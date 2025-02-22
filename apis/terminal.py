import subprocess
import time
from typing import Optional, Union


# Custom Exceptions
class CommandTimeoutError(Exception):
    pass


class CommandExecutionError(Exception):
    pass


class TerminalCommandsExecutor:
    def __init__(self, logger, max_retries: int = 3, retry_backoff_factor: int = 2, verbose: bool = False):
        if max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer.")
        if retry_backoff_factor <= 0:
            raise ValueError("retry_backoff_factor must be positive.")

        self.logger = logger
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.verbose = verbose  # Verbose mode

    def run_terminal_command(self, command: str, wait: bool = False, stream_output: bool = True,
                             timeout: Optional[int] = None) -> Optional[Union[subprocess.Popen, str]]:
        attempt = 0
        error_msgs = []

        while attempt < self.max_retries:
            try:
                stdout = subprocess.PIPE if stream_output or self.verbose else subprocess.DEVNULL
                stderr = subprocess.PIPE

                # self.logger.info(f"Executing command: {command}")  # Log the command being run

                if wait:
                    result = subprocess.run(command, shell=True, universal_newlines=True, stdout=stdout,
                                            stderr=stderr, check=False, timeout=timeout)

                    if result.returncode == 0:
                        self.logger.info(f"Execution status code {result.returncode}.")
                        if self.verbose or stream_output:
                            self.logger.info(result)
                        return result.stdout.strip() if result.stdout else 'True'
                    else:
                        if 'dfsadmin' in command:
                            return result.stdout.strip() if result.stdout else ''
                        # TODO: add special case for hdfs admin report
                        error_msgs.append(result.stderr)
                        self.logger.error(f"Attempt {attempt + 1}/{self.max_retries}: Error: {result.stderr}")
                        time.sleep(self.retry_backoff_factor ** attempt)
                        attempt += 1
                else:
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=stdout,
                        stderr=stderr
                    )
                    return process

            except subprocess.TimeoutExpired:
                self.logger.error(f"Attempt {attempt + 1}/{self.max_retries}: Command timed out.")
                error_msgs.append("Command timed out.")
                attempt += 1
                time.sleep(self.retry_backoff_factor ** attempt)
            except subprocess.SubprocessError as e:
                self.logger.error(f"Attempt {attempt + 1}/{self.max_retries}: Subprocess error: {e}")
                error_msgs.append(str(e))
                raise CommandExecutionError(f"Subprocess error: {e}")
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1}/{self.max_retries}: An unexpected error occurred: {e}")
                error_msgs.append(str(e))
                raise CommandExecutionError(f"Unexpected error: {e}")

        if attempt == self.max_retries:
            self.logger.error(f"All retries failed for command: {command}. Errors: {error_msgs}")
            raise CommandExecutionError(f"Command failed after {self.max_retries} attempts.")

        return ''

    def terminate_process(self, process: subprocess.Popen) -> None:
        """
        Gracefully terminates a running subprocess.

        :param process: The subprocess to terminate.
        :raises CommandExecutionError: If the process could not be terminated.
        """
        try:
            process.terminate()
            process.wait(timeout=10)
            self.logger.info("Process terminated successfully.")
        except subprocess.TimeoutExpired:
            self.logger.error("Process termination timed out. Killing process.")
            process.kill()
            raise CommandExecutionError("Failed to terminate process gracefully.")

    def execute(self, command: str, wait: bool = False, stream_output: bool = True,
                timeout: Optional[int] = None) -> bool:
        """
        Executes a command and handles logging and retries.

        :param command: The command to execute.
        :param wait: If True, waits for the command to complete.
        :param stream_output: If True, streams the command's output.
        :param timeout: The maximum time in seconds to allow the command to run.
        :return: True if the command was successful, False otherwise.
        """
        self.logger.info(f"Start running the command: {command}.")
        try:
            res = self.run_terminal_command(
                command,
                wait,
                stream_output,
                timeout
            )

            if wait:
                if res:
                    self.logger.info(f"Finished running: {command}... with status success")
                else:
                    self.logger.error(f"Finished running: {command}... with status failed", 'error')
                    return False
            else:
                if isinstance(res, subprocess.Popen):
                    self.logger.info(f"Command is running in the background: {command}")
                    return True
                else:
                    self.logger.error(f"Failed to start the command: {command}", 'error')
                    return False

            return True
        except CommandTimeoutError as e:
            self.logger.error(f"Command timed out: {e}", 'error')
            return False
        except CommandExecutionError as e:
            self.logger.error(f"Command execution failed: {e}", 'error')
            return False
