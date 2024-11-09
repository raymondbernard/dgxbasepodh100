import paramiko

# SSH server details
hostname = 'worker10.air.nvidia.com'
port = 27907  # default SSH port
username = 'ubuntu'
password = None  # set your password or leave as None if using a private key
key_file_path = 'airnvidiakey.pem'  # set path to your private key file (in PEM format) or leave as None if using a password

# Initialize SSH client
ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    # Connect to the SSH server
    if key_file_path:
        ssh_client.connect(hostname, port, username, key_filename=key_file_path, look_for_keys=False, allow_agent=False)
    elif password:
        ssh_client.connect(hostname, port, username, password, look_for_keys=False, allow_agent=False)
    else:
        print("Authentication method required. Please provide a password or private key file.")
        exit(1)

    # Run a simple command (e.g., 'ls -l')
    stdin, stdout, stderr = ssh_client.exec_command('ls -l')
    print("Command output:")
    print(stdout.read().decode())

except paramiko.AuthenticationException:
    print("Authentication failed, please verify your credentials")
except paramiko.SSHException as e:
    print(f"SSH error: {str(e)}")
finally:
    ssh_client.close()
