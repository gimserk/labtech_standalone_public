from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Max
from app.models import ProxmoxServer, StudentVMIDPool

User = get_user_model()

class Command(BaseCommand):
    help = 'Assigns VMID pools to all existing users who do not have one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pool-size',
            type=int,
            default=5,
            help='The number of VMIDs to assign to each user per server.',
        )

    def handle(self, *args, **options):
        pool_size = options['pool_size']
        self.stdout.write(self.style.SUCCESS(f"Starting assignment of VMID pools with a size of {pool_size}..."))

        servers = ProxmoxServer.objects.filter(
            vmid_range_start__isnull=False,
            vmid_range_end__isnull=False
        )

        if not servers.exists():
            self.stdout.write(self.style.WARNING("No Proxmox servers with defined VMID ranges found. Exiting."))
            return

        all_users = User.objects.all()
        created_count = 0

        for server in servers:
            self.stdout.write(f"\nProcessing server: {server.name}")
            
            # Find the highest currently assigned VMID on this server to know where to start.
            last_assigned_vmid = StudentVMIDPool.objects.filter(
                proxmox_server=server
            ).aggregate(max_end=Max('vmid_end'))['max_end']

            next_start_vmid = last_assigned_vmid + 1 if last_assigned_vmid else server.vmid_range_start

            # Get a list of users who ALREADY have a pool on this specific server
            users_with_pool = StudentVMIDPool.objects.filter(
                proxmox_server=server
            ).values_list('user_id', flat=True)

            users_to_provision = all_users.exclude(id__in=users_with_pool)

            if not users_to_provision.exists():
                self.stdout.write(f"  All users already have a pool on {server.name}.")
                continue

            for user in users_to_provision:
                pool_end_vmid = next_start_vmid + (pool_size - 1)

                if pool_end_vmid > server.vmid_range_end:
                    self.stdout.write(self.style.ERROR(
                        f"  Not enough VMIDs left on server {server.name} to create a pool for {user.username}. "
                        f"Required: {pool_end_vmid}, Available up to: {server.vmid_range_end}. Halting for this server."
                    ))
                    break # Stop processing for this server as we've run out of space

                StudentVMIDPool.objects.create(
                    user=user,
                    proxmox_server=server,
                    vmid_start=next_start_vmid,
                    vmid_end=pool_end_vmid
                )
                self.stdout.write(f"  - Created pool {next_start_vmid}-{pool_end_vmid} for {user.username}")
                created_count += 1
                
                # The start for the *next* user is the end of the current user's pool + 1
                next_start_vmid = pool_end_vmid + 1

        self.stdout.write(self.style.SUCCESS(f"\nProcess complete. Created {created_count} new VMID pool(s)."))