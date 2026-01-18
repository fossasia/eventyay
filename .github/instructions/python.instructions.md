---
applyTo: "**/*.py"
---

# Python Development Instructions

## Import

The import lines should be on the top of the file, not inside functions, except when there is circular import error.

## Logging

- When the logging message needs to be constructed from multiple parts or variables, don't use f-string or any method that builds the string before passing to the logger. Instead, use the logger's built-in string interpolation feature. For example, use `logger.info('User %s has logged in', username)` instead of `logger.info(f"User {username} has logged in")`. This is to avoid wasting computation when log level doesn't match.

- Avoid catching general exceptions like `Exception` or `BaseException`. Instead, catch specific exceptions that you expect to handle. It is because, we want to expose errors originating from developer mistakes to fix them early.

- When generating log as part of exception handling, don't wrap the exception object with `str()`. For example, don't do:

  ```python
  except SomeException as e:
      logger.error('An error occurred: %s', str(e))
  ```

  Just do:

  ```python
  except SomeException as e:
      logger.error('An error occurred: %s', e)
  ```

- When generating log, if using `logger.exception()`, no need to pass the exception object as part of the log message. For example, don't do:

  ```python
  except SomeException as e:
      logger.exception('An error occurred: %s', e)
  ```

  Just do:

  ```python
  except SomeException:
      logger.exception('An error occurred')
  ```

  because `logger.exception()` automatically includes the stack trace of the caught exception.

- When stringifying datetime data, prefer using f-string with specifiers to `.strftime()`. For example, use `f"{dt:%Y-%m-%d %H:%M:%S}"` instead of `dt.strftime("%Y-%m-%d %H:%M:%S")`.

- When you are about to embed a datetime data to another string, don't stringify the datetime before embedding. For example, don't do:

  ```py
  now = datetime.now().strftime('%Y%m%d-%H%M%S')
  filename = f'export-{now}.csv'
  ```

  Just do:

  ```py
  now = datetime.now()
  filename = f'export-{now:%Y%m%d-%H%M%S}.csv'
  ```

  The idea is that, if we have a variable to keep datetime, we should keep the most precise data.

- When stringifying objects with f-string, no need to wrap the object with `str()`. For example, don't do `f"Value is {str(value)}"`. Just do `f"Value is {value}"`.

## Function Definitions

- When defining functions, methods and variables, don't make them private (_prefix) unless there is a strong reason to do so. Private functions are not common in Python.

- Don't define class method if it doesn't use the `self` parameter. Use normal functions instead, to keep the code flat.

## REST API

- When defining DjangoRestFramework serializer, avoid `SerializerMethodField` because looking at it, it is difficult to know the shape of data that the field will return.

## Django command

- When defining Django command, declare parameters explicitly in `handle()` method, not retrieve them from `options` dictionary.
