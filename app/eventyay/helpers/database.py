import contextlib

from django.db import connection, connections, transaction
from django.db.models import Aggregate, Field, Lookup
from django.db.models.expressions import OrderBy
from django.utils.functional import lazy


class DummyRollbackException(Exception):  # NOQA: N818
    pass


@contextlib.contextmanager
def rolledback_transaction():
    """
    This context manager runs your code in a database transaction that will be rolled back in the end.
    This can come in handy to simulate the effects of a database operation that you do not actually
    want to perform.

    Note that rollbacks are a very slow operation on most database backends. Also, long-running
    transactions can slow down other operations currently running and you should not use this
    in a place that is called frequently.
    """
    try:
        with transaction.atomic():
            yield
            raise DummyRollbackException()
    except DummyRollbackException:
        pass
    else:
        raise Exception('Invalid state, should have rolled back.')


@contextlib.contextmanager
def casual_reads():
    """
    Kept for backwards compatibility.
    """
    yield


class FixedOrderBy(OrderBy):
    # Workaround for https://code.djangoproject.com/ticket/28848
    template = '%(expression)s %(ordering)s'

    def as_sql(self, compiler, connection, template=None, **extra_context):
        if not template:
            if self.nulls_last:
                template = '%s NULLS LAST' % self.template
            elif self.nulls_first:
                template = '%s NULLS FIRST' % self.template
        connection.ops.check_expression_support(self)
        expression_sql, params = compiler.compile(self.expression)
        placeholders = {
            'expression': expression_sql,
            'ordering': 'DESC' if self.descending else 'ASC',
        }
        placeholders.update(extra_context)
        template = template or self.template
        params = params * template.count('%(expression)s')
        return (template % placeholders).rstrip(), params


class GroupConcat(Aggregate):
    function = 'group_concat'
    template = '%(function)s(%(field)s, "%(separator)s")'

    def __init__(self, *expressions, **extra):
        if 'separator' not in extra:
            # For PostgreSQL separator is an obligatory
            extra.update({'separator': ','})
        super().__init__(*expressions, **extra)

    def as_postgresql(self, compiler, connection):
        return super().as_sql(
            compiler,
            connection,
            function='string_agg',
            template="%(function)s(%(field)s::text, '%(separator)s')",
        )


class ReplicaRouter:
    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        db_list = ('default', 'replica')
        if obj1._state.db in db_list and obj2._state.db in db_list:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hintrs):
        return True


@Field.register_lookup
class NotEqual(Lookup):
    lookup_name = 'ne'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s <> %s' % (lhs, rhs), params


def _of_self():
    return ('self',) if connection.features.has_select_for_update_of else ()


OF_SELF = lazy(_of_self, tuple)()


def lock_rows_shared(queryset):
    """Lock a fixed set of rows for reading without waiting on partial locks.

    Call inside an atomic block and load only the returned IDs afterwards.
    PostgreSQL shared locks allow independent readers while excluding updates.
    """
    database = connections[queryset.db]
    if database.vendor != 'postgresql':
        return list(queryset.order_by('pk').select_for_update().values_list('pk', flat=True))
    if not database.in_atomic_block:
        raise transaction.TransactionManagementError('Shared row locks require a transaction.')
    ids = list(queryset.order_by('pk').values_list('pk', flat=True))
    if not ids:
        return []
    table = database.ops.quote_name(queryset.model._meta.db_table)
    pk = database.ops.quote_name(queryset.model._meta.pk.column)
    with database.cursor() as cursor:
        cursor.execute(f'SELECT {pk} FROM {table} WHERE {pk} = ANY(%s) ORDER BY {pk} FOR SHARE NOWAIT', [ids])
        return [row[0] for row in cursor.fetchall()]


def try_transaction_lock(name: str, using: str = 'default') -> bool:
    """Try a PostgreSQL transaction-scoped mutex without locking an account row."""
    database = connections[using]
    if database.vendor != 'postgresql':
        return True
    if not database.in_atomic_block:
        raise transaction.TransactionManagementError('Transaction locks require a transaction.')
    with database.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))', [name])
        return cursor.fetchone()[0]


def lock_m2m_parents(model, field, instance, action, reverse, pk_set, using):
    """Lock relation owners before a many-to-many insertion or deletion.

    Django emits pre-change signals inside the relation's transaction. Locking
    parents first also protects absent relationships and avoids delete/insert
    lock inversions with shared parent readers.
    """
    if action not in ('pre_add', 'pre_remove', 'pre_clear'):
        return
    parents = model.objects.using(using)
    if reverse:
        parents = parents.filter(pk__in=pk_set) if pk_set is not None else parents.filter(**{field: instance})
    else:
        parents = parents.filter(pk=instance.pk)
    list(parents.order_by('pk').select_for_update(of=OF_SELF))
