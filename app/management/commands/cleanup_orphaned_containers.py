import paramiko
from django.core.management.base import BaseCommand
from app.models import DockerServer, LabInstanceMachine, CyberCityMachine

class Command(BaseCommand):
    help = 'Finds and removes orphaned Docker containers on all registered Docker Servers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lists orphaned containers without actually removing them.',
        )

    def handle(self, *args, **options):
        is_dry_run = options['dry_run']

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE: No containers will be removed. ==="))

        # Get all container IDs that Django knows about and thinks are active
        known_lab_ids = set(LabInstanceMachine.objects.values_list('docker_container_id', flat=True))
        known_cybercity_ids = set(CyberCityMachine.objects.values_list('docker_container_id', flat=True))
        all_known_ids = {str(id) for id in (known_lab_ids | known_cybercity_ids) if id}

        self.stdout.write(f"Found {len(all_known_ids)} known, active containers in the database.")

        # Iterate through each registered Docker Server
        for server in DockerServer.objects.all():
            self.stdout.write(self.style.HTTP_INFO(f"\n--- Checking Docker Server: {server.name} ({server.host}) ---"))
            
            try:
                # Get all container IDs that actually exist on the server
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client.connect(server.host, port=server.ssh_port, username=server.ssh_user, password=server.ssh_password_or_key, timeout=10)
                
                # Command to list all container IDs (first 12 chars is enough)
                _, stdout, stderr = ssh_client.exec_command("docker ps -a --format '{{.ID}}'")
                
                if stderr.read():
                    raise Exception(f"Docker command error: {stderr.read().decode()}")

                actual_ids_on_host = set(stdout.read().decode().split())
                self.stdout.write(f"Found {len(actual_ids_on_host)} total containers on this host.")

                # Find the orphans by subtracting the known set from the actual set
                orphaned_ids = actual_ids_on_host - all_known_ids

                if not orphaned_ids:
                    self.stdout.write(self.style.SUCCESS("No orphaned containers found."))
                    continue

                self.stdout.write(self.style.WARNING(f"Found {len(orphaned_ids)} orphaned container(s):"))
                for orphan_id in orphaned_ids:
                    self.stdout.write(f"  - {orphan_id}")

                if not is_dry_run:
                    self.stdout.write("--- Removing orphaned containers... ---")
                    # Create a single command to remove all orphans at once
                    cleanup_command = "docker rm -f " + " ".join(orphaned_ids)
                    _, stdout, stderr = ssh_client.exec_command(cleanup_command)
                    
                    removed_list = stdout.read().decode().strip()
                    error_output = stderr.read().decode().strip()

                    if removed_list:
                         self.stdout.write(self.style.SUCCESS(f"Successfully removed: {removed_list.replace('/n', ', ')}"))
                    if error_output:
                        self.stdout.write(self.style.ERROR(f"Errors during removal: {error_output}"))
                
                ssh_client.close()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Could not audit server {server.name}. Error: {e}"))

        self.stdout.write(self.style.SUCCESS("\nAudit complete."))