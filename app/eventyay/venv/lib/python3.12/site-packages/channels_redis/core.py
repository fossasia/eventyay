import asyncio
import collections
import functools
import itertools
import logging
import time
import uuid

from redis import asyncio as aioredis

from channels.exceptions import ChannelFull
from channels.layers import BaseChannelLayer

from .serializers import registry
from .utils import (
    _close_redis,
    _consistent_hash,
    _wrap_close,
    create_pool,
    decode_hosts,
)

logger = logging.getLogger(__name__)


class ChannelLock:
    """
    Helper class for per-channel locking.

    Once a lock is released and has no waiters, it will also be deleted,
    to mitigate multi-event loop problems.
    """

    def __init__(self):
        self.locks = collections.defaultdict(asyncio.Lock)
        self.wait_counts = collections.defaultdict(int)

    async def acquire(self, channel):
        """
        Acquire the lock for the given channel.
        """
        self.wait_counts[channel] += 1
        return await self.locks[channel].acquire()

    def locked(self, channel):
        """
        Return ``True`` if the lock for the given channel is acquired.
        """
        return self.locks[channel].locked()

    def release(self, channel):
        """
        Release the lock for the given channel.
        """
        self.locks[channel].release()
        self.wait_counts[channel] -= 1
        if self.wait_counts[channel] < 1:
            del self.locks[channel]
            del self.wait_counts[channel]


class BoundedQueue(asyncio.Queue):
    def put_nowait(self, item):
        if self.full():
            # see: https://github.com/django/channels_redis/issues/212
            # if we actually get into this code block, it likely means that
            # this specific consumer has stopped reading
            # if we get into this code block, it's better to drop messages
            # that exceed the channel layer capacity than to continue to
            # malloc() forever
            self.get_nowait()
        return super(BoundedQueue, self).put_nowait(item)


class RedisLoopLayer:
    def __init__(self, channel_layer):
        self._lock = asyncio.Lock()
        self.channel_layer = channel_layer
        self._connections = {}

    def get_connection(self, index):
        if index not in self._connections:
            pool = self.channel_layer.create_pool(index)
            self._connections[index] = aioredis.Redis(connection_pool=pool)

        return self._connections[index]

    async def flush(self):
        async with self._lock:
            for index in list(self._connections):
                connection = self._connections.pop(index)
                await _close_redis(connection)


class RedisChannelLayer(BaseChannelLayer):
    """
    Redis channel layer.

    It routes all messages into remote Redis server. Support for
    sharding among different Redis installations and message
    encryption are provided.
    """

    brpop_timeout = 5

    def __init__(
        self,
        hosts=None,
        prefix="asgi",
        expiry=60,
        group_expiry=86400,
        capacity=100,
        channel_capacity=None,
        symmetric_encryption_keys=None,
        random_prefix_length=12,
        serializer_format="msgpack",
    ):
        # Store basic information
        self.expiry = expiry
        self.group_expiry = group_expiry
        self.capacity = capacity
        self.channel_capacity = self.compile_capacities(channel_capacity or {})
        self.prefix = prefix
        assert isinstance(self.prefix, str), "Prefix must be unicode"
        # Configure the host objects
        self.hosts = decode_hosts(hosts)
        self.ring_size = len(self.hosts)
        # serialization
        self._serializer = registry.get_serializer(
            serializer_format,
            # As we use an sorted set to expire messages we need to guarantee uniqueness, with 12 bytes.
            random_prefix_length=random_prefix_length,
            expiry=self.expiry,
            symmetric_encryption_keys=symmetric_encryption_keys,
        )
        # Cached redis connection pools and the event loop they are from
        self._layers = {}
        # Normal channels choose a host index by cycling through the available hosts
        self._receive_index_generator = itertools.cycle(range(len(self.hosts)))
        self._send_index_generator = itertools.cycle(range(len(self.hosts)))
        # Decide on a unique client prefix to use in ! sections
        self.client_prefix = uuid.uuid4().hex
        # Number of coroutines trying to receive right now
        self.receive_count = 0
        # The receive lock
        self.receive_lock = None
        # Event loop they are trying to receive on
        self.receive_event_loop = None
        # Buffered messages by process-local channel name
        self.receive_buffer = collections.defaultdict(
            functools.partial(BoundedQueue, self.capacity)
        )
        # Detached channel cleanup tasks
        self.receive_cleaners = []
        # Per-channel cleanup locks to prevent a receive starting and moving
        # a message back into the main queue before its cleanup has completed
        self.receive_clean_locks = ChannelLock()

    def create_pool(self, index):
        return create_pool(self.hosts[index])

    ### Channel layer API ###

    extensions = ["groups", "flush"]

    async def send(self, channel, message):
        """
        Send a message onto a (general or specific) channel.
        """
        # Typecheck
        assert isinstance(message, dict), "message is not a dict"
        assert self.require_valid_channel_name(channel), "Channel name not valid"
        # Make sure the message does not contain reserved keys
        assert "__asgi_channel__" not in message
        # If it's a process-local channel, strip off local part and stick full name in message
        channel_non_local_name = channel
        if "!" in channel:
            message = dict(message.items())
            message["__asgi_channel__"] = channel
            channel_non_local_name = self.non_local_name(channel)
        # Write out message into expiring key (avoids big items in list)
        channel_key = self.prefix + channel_non_local_name
        # Pick a connection to the right server - consistent for specific
        # channels, random for general channels
        if "!" in channel:
            index = self.consistent_hash(channel)
        else:
            index = next(self._send_index_generator)
        connection = self.connection(index)
        # Discard old messages based on expiry
        await connection.zremrangebyscore(
            channel_key, min=0, max=int(time.time()) - int(self.expiry)
        )

        # Check the length of the list before send
        # This can allow the list to leak slightly over capacity, but that's fine.
        if await connection.zcount(channel_key, "-inf", "+inf") >= self.get_capacity(
            channel
        ):
            raise ChannelFull()

        # Push onto the list then set it to expire in case it's not consumed
        await connection.zadd(channel_key, {self.serialize(message): time.time()})
        await connection.expire(channel_key, int(self.expiry))

    def _backup_channel_name(self, channel):
        """
        Construct the key used as a backup queue for the given channel.
        """
        return channel + "$inflight"

    async def _brpop_with_clean(self, index, channel, timeout):
        """
        Perform a Redis BRPOP and manage the backup processing queue.
        In case of cancellation, make sure the message is not lost.
        """
        # The script will pop messages from the processing queue and push them in front
        # of the main message queue in the proper order; BRPOP must *not* be called
        # because that would deadlock the server
        cleanup_script = """
            local backed_up = redis.call('ZRANGE', ARGV[2], 0, -1, 'WITHSCORES')
            for i = #backed_up, 1, -2 do
                redis.call('ZADD', ARGV[1], backed_up[i], backed_up[i - 1])
            end
            redis.call('DEL', ARGV[2])
        """
        backup_queue = self._backup_channel_name(channel)
        connection = self.connection(index)
        # Cancellation here doesn't matter, we're not doing anything destructive
        # and the script executes atomically...
        await connection.eval(cleanup_script, 0, channel, backup_queue)
        # ...and it doesn't matter here either, the message will be safe in the backup.
        result = await connection.bzpopmin(channel, timeout=timeout)

        if result is not None:
            _, member, timestamp = result
            await connection.zadd(backup_queue, {member: float(timestamp)})
        else:
            member = None

        return member

    async def _clean_receive_backup(self, index, channel):
        """
        Pop the oldest message off the channel backup queue.
        The result isn't interesting as it was already processed.
        """
        connection = self.connection(index)
        await connection.zpopmin(self._backup_channel_name(channel))

    async def receive(self, channel):
        """
        Receive the first message that arrives on the channel.
        If more than one coroutine waits on the same channel, the first waiter
        will be given the message when it arrives.
        """
        # Make sure the channel name is valid then get the non-local part
        # and thus its index
        assert self.require_valid_channel_name(channel)
        if "!" in channel:
            real_channel = self.non_local_name(channel)
            assert real_channel.endswith(
                self.client_prefix + "!"
            ), "Wrong client prefix"
            # Enter receiving section
            loop = asyncio.get_running_loop()
            self.receive_count += 1
            try:
                if self.receive_count == 1:
                    # If we're the first coroutine in, create the receive lock!
                    self.receive_lock = asyncio.Lock()
                    self.receive_event_loop = loop
                else:
                    # Otherwise, check our event loop matches
                    if self.receive_event_loop != loop:
                        raise RuntimeError(
                            "Two event loops are trying to receive() on one channel layer at once!"
                        )

                # Wait for our message to appear
                message = None
                while self.receive_buffer[channel].empty():
                    tasks = [
                        self.receive_lock.acquire(),
                        self.receive_buffer[channel].get(),
                    ]
                    tasks = [asyncio.ensure_future(task) for task in tasks]
                    try:
                        done, pending = await asyncio.wait(
                            tasks, return_when=asyncio.FIRST_COMPLETED
                        )
                        for task in pending:
                            # Cancel all pending tasks.
                            task.cancel()
                    except asyncio.CancelledError:
                        # Ensure all tasks are cancelled if we are cancelled.
                        # Also see: https://bugs.python.org/issue23859
                        del self.receive_buffer[channel]
                        for task in tasks:
                            if not task.cancel():
                                assert task.done()
                                if task.result() is True:
                                    self.receive_lock.release()

                        raise

                    message = token = exception = None
                    for task in done:
                        try:
                            result = task.result()
                        except BaseException as error:  # NOQA
                            # We should not propagate exceptions immediately as otherwise this may cause
                            # the lock to be held and never be released.
                            exception = error
                            continue

                        if result is True:
                            token = result
                        else:
                            assert isinstance(result, dict)
                            message = result

                    if message or exception:
                        if token:
                            # We will not be receving as we already have the message.
                            self.receive_lock.release()

                        if exception:
                            raise exception
                        else:
                            break
                    else:
                        assert token

                        # We hold the receive lock, receive and then release it.
                        try:
                            # There is no interruption point from when the message is
                            # unpacked in receive_single to when we get back here, so
                            # the following lines are essentially atomic.
                            message_channel, message = await self.receive_single(
                                real_channel
                            )
                            if isinstance(message_channel, list):
                                for chan in message_channel:
                                    self.receive_buffer[chan].put_nowait(message)
                            else:
                                self.receive_buffer[message_channel].put_nowait(message)
                            message = None
                        except Exception:
                            del self.receive_buffer[channel]
                            raise
                        finally:
                            self.receive_lock.release()

                # We know there's a message available, because there
                # couldn't have been any interruption between empty() and here
                if message is None:
                    message = self.receive_buffer[channel].get_nowait()

                if self.receive_buffer[channel].empty():
                    del self.receive_buffer[channel]
                return message

            finally:
                self.receive_count -= 1
                # If we were the last out, drop the receive lock
                if self.receive_count == 0:
                    assert not self.receive_lock.locked()
                    self.receive_lock = None
                    self.receive_event_loop = None
        else:
            # Do a plain direct receive
            return (await self.receive_single(channel))[1]

    async def receive_single(self, channel):
        """
        Receives a single message off of the channel and returns it.
        """
        # Check channel name
        assert self.require_valid_channel_name(
            channel, receive=True
        ), "Channel name invalid"
        # Work out the connection to use
        if "!" in channel:
            assert channel.endswith("!")
            index = self.consistent_hash(channel)
        else:
            index = next(self._receive_index_generator)

        channel_key = self.prefix + channel
        content = None
        await self.receive_clean_locks.acquire(channel_key)
        try:
            while content is None:
                # Nothing is lost here by cancellations, messages will still
                # be in the backup queue.
                content = await self._brpop_with_clean(
                    index, channel_key, timeout=self.brpop_timeout
                )

            # Fire off a task to clean the message from its backup queue.
            # Per-channel locking isn't needed, because the backup is a queue
            # and additionally, we don't care about the order; all processed
            # messages need to be removed, no matter if the current one is
            # removed after the next one.
            # NOTE: Duplicate messages will be received eventually if any
            # of these cleaners are cancelled.
            cleaner = asyncio.ensure_future(
                self._clean_receive_backup(index, channel_key)
            )
            self.receive_cleaners.append(cleaner)

            def _cleanup_done(cleaner):
                self.receive_cleaners.remove(cleaner)
                self.receive_clean_locks.release(channel_key)

            cleaner.add_done_callback(_cleanup_done)

        except BaseException:
            self.receive_clean_locks.release(channel_key)
            raise

        # Message decode
        message = self.deserialize(content)
        # TODO: message expiry?
        # If there is a full channel name stored in the message, unpack it.
        if "__asgi_channel__" in message:
            channel = message["__asgi_channel__"]
            del message["__asgi_channel__"]
        return channel, message

    async def new_channel(self, prefix="specific"):
        """
        Returns a new channel name that can be used by something in our
        process as a specific channel.
        """
        return f"{prefix}.{self.client_prefix}!{uuid.uuid4().hex}"

    ### Flush extension ###

    async def flush(self):
        """
        Deletes all messages and groups on all shards.
        """
        # Make sure all channel cleaners have finished before removing
        # keys from under their feet.
        await self.wait_received()

        # Lua deletion script
        delete_prefix = """
            local keys = redis.call('keys', ARGV[1])
            for i=1,#keys,5000 do
                redis.call('del', unpack(keys, i, math.min(i+4999, #keys)))
            end
        """
        # Go through each connection and remove all with prefix
        for i in range(self.ring_size):
            connection = self.connection(i)
            await connection.eval(delete_prefix, 0, self.prefix + "*")
        # Now clear the pools as well
        await self.close_pools()

    async def close_pools(self):
        """
        Close all connections in the event loop pools.
        """
        # Flush all cleaners, in case somebody just wanted to close the
        # pools without flushing first.
        await self.wait_received()
        for layer in self._layers.values():
            await layer.flush()

    async def wait_received(self):
        """
        Wait for all channel cleanup functions to finish.
        """
        if self.receive_cleaners:
            await asyncio.wait(self.receive_cleaners[:])

    ### Groups extension ###

    async def group_add(self, group, channel):
        """
        Adds the channel name to a group.
        """
        # Check the inputs
        assert self.require_valid_group_name(group), "Group name not valid"
        assert self.require_valid_channel_name(channel), "Channel name not valid"
        # Get a connection to the right shard
        group_key = self._group_key(group)
        connection = self.connection(self.consistent_hash(group))
        # Add to group sorted set with creation time as timestamp
        await connection.zadd(group_key, {channel: time.time()})
        # Set expiration to be group_expiry, since everything in
        # it at this point is guaranteed to expire before that
        await connection.expire(group_key, self.group_expiry)

    async def group_discard(self, group, channel):
        """
        Removes the channel from the named group if it is in the group;
        does nothing otherwise (does not error)
        """
        assert self.require_valid_group_name(group), "Group name not valid"
        assert self.require_valid_channel_name(channel), "Channel name not valid"
        key = self._group_key(group)
        connection = self.connection(self.consistent_hash(group))
        await connection.zrem(key, channel)

    async def group_send(self, group, message):
        """
        Sends a message to the entire group.
        """
        assert self.require_valid_group_name(group), "Group name not valid"
        # Retrieve list of all channel names
        key = self._group_key(group)
        connection = self.connection(self.consistent_hash(group))
        # Discard old channels based on group_expiry
        await connection.zremrangebyscore(
            key, min=0, max=int(time.time()) - self.group_expiry
        )

        channel_names = [x.decode("utf8") for x in await connection.zrange(key, 0, -1)]

        (
            connection_to_channel_keys,
            channel_keys_to_message,
            channel_keys_to_capacity,
        ) = self._map_channel_keys_to_connection(channel_names, message)

        for connection_index, channel_redis_keys in connection_to_channel_keys.items():
            # Discard old messages based on expiry
            pipe = connection.pipeline()
            for key in channel_redis_keys:
                pipe.zremrangebyscore(
                    key, min=0, max=int(time.time()) - int(self.expiry)
                )
            await pipe.execute()

            # Create a LUA script specific for this connection.
            # Make sure to use the message specific to this channel, it is
            # stored in channel_to_message dict and contains the
            # __asgi_channel__ key.

            group_send_lua = """
                local over_capacity = 0
                local current_time = ARGV[#ARGV - 1]
                local expiry = ARGV[#ARGV]
                for i=1,#KEYS do
                    if redis.call('ZCOUNT', KEYS[i], '-inf', '+inf') < tonumber(ARGV[i + #KEYS]) then
                        redis.call('ZADD', KEYS[i], current_time, ARGV[i])
                        redis.call('EXPIRE', KEYS[i], expiry)
                    else
                        over_capacity = over_capacity + 1
                    end
                end
                return over_capacity
            """

            # We need to filter the messages to keep those related to the connection
            args = [
                channel_keys_to_message[channel_key]
                for channel_key in channel_redis_keys
            ]

            # We need to send the capacity for each channel
            args += [
                channel_keys_to_capacity[channel_key]
                for channel_key in channel_redis_keys
            ]

            args += [time.time(), self.expiry]

            # channel_keys does not contain a single redis key more than once
            connection = self.connection(connection_index)
            channels_over_capacity = await connection.eval(
                group_send_lua, len(channel_redis_keys), *channel_redis_keys, *args
            )
            if channels_over_capacity > 0:
                logger.info(
                    "%s of %s channels over capacity in group %s",
                    channels_over_capacity,
                    len(channel_names),
                    group,
                )

    def _map_channel_keys_to_connection(self, channel_names, message):
        """
        For a list of channel names, GET

        1. list of their redis keys bucket each one to a dict keyed by the connection index

        2. for each unique channel redis key create a serialized message specific to that redis key, by adding
           the list of channels mapped to that redis key in __asgi_channel__ key to the message

        3. returns a mapping of redis channels keys to their capacity
        """

        # Connection dict keyed by index to list of redis keys mapped on that index
        connection_to_channel_keys = collections.defaultdict(list)
        # Message dict maps redis key to the message that needs to be send on that key
        channel_key_to_message = dict()
        # Channel key mapped to its capacity
        channel_key_to_capacity = dict()

        # For each channel
        for channel in channel_names:
            channel_non_local_name = channel
            if "!" in channel:
                channel_non_local_name = self.non_local_name(channel)
            # Get its redis key
            channel_key = self.prefix + channel_non_local_name
            # Have we come across the same redis key?
            if channel_key not in channel_key_to_message:
                # If not, fill the corresponding dicts
                message = dict(message.items())
                message["__asgi_channel__"] = [channel]
                channel_key_to_message[channel_key] = message
                channel_key_to_capacity[channel_key] = self.get_capacity(channel)
                idx = self.consistent_hash(channel_non_local_name)
                connection_to_channel_keys[idx].append(channel_key)
            else:
                # Yes, Append the channel in message dict
                channel_key_to_message[channel_key]["__asgi_channel__"].append(channel)

        # Now that we know what message needs to be send on a redis key we serialize it
        for key, value in channel_key_to_message.items():
            # Serialize the message stored for each redis key
            channel_key_to_message[key] = self.serialize(value)

        return (
            connection_to_channel_keys,
            channel_key_to_message,
            channel_key_to_capacity,
        )

    def _group_key(self, group):
        """
        Common function to make the storage key for the group.
        """
        return f"{self.prefix}:group:{group}".encode("utf8")

    ### Serialization ###

    def serialize(self, message):
        """
        Serializes message to a byte string.
        """
        return self._serializer.serialize(message)

    def deserialize(self, message):
        """
        Deserializes from a byte string.
        """
        return self._serializer.deserialize(message)

    ### Internal functions ###

    def consistent_hash(self, value):
        return _consistent_hash(value, self.ring_size)

    def __str__(self):
        return f"{self.__class__.__name__}(hosts={self.hosts})"

    ### Connection handling ###

    def connection(self, index):
        """
        Returns the correct connection for the index given.
        Lazily instantiates pools.
        """
        # Catch bad indexes
        if not 0 <= index < self.ring_size:
            raise ValueError(
                f"There are only {self.ring_size} hosts - you asked for {index}!"
            )

        loop = asyncio.get_running_loop()
        try:
            layer = self._layers[loop]
        except KeyError:
            _wrap_close(self, loop)
            layer = self._layers[loop] = RedisLoopLayer(self)

        return layer.get_connection(index)
