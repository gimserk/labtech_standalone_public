import os
import stat
import logging
from django.core.management.base import BaseCommand
from app.models import VPNProfile

# Configure logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Syncs VPN profiles from the database to systemd-readable config files in /etc/openvpn/client/'

    def handle(self, *args, **options):
        if os.geteuid() != 0:
            self.stdout.write(self.style.ERROR("This command must be run as root (or with sudo)."))
            return

        self.stdout.write("Starting VPN profile sync...")
        
        config_dir = "/etc/openvpn/client"
        if not os.path.isdir(config_dir):
            self.stdout.write(self.style.ERROR(f"Configuration directory {config_dir} does not exist."))
            return

        profiles = VPNProfile.objects.all()
        for profile in profiles:
            if not profile.ovpn_file:
                self.stdout.write(self.style.WARNING(f"Skipping profile '{profile.name}' because it has no .ovpn file."))
                continue

            conf_path = profile.symlink_path  # e.g., /etc/openvpn/client/labtech-vpn-1.conf
            auth_path = f"/etc/openvpn/client/{profile.config_base_name}.auth"
            
            try:
                # Read the original .ovpn file content
                original_content = profile.ovpn_file.read().decode('utf-8')
                new_content_lines = []
                auth_line_found = False

                # Modify the content to point to the new auth file
                for line in original_content.splitlines():
                    if line.strip().startswith('auth-user-pass'):
                        new_content_lines.append(f'auth-user-pass {auth_path}')
                        auth_line_found = True
                    else:
                        new_content_lines.append(line)
                
                # If no auth-user-pass line exists but we have credentials, add one
                if not auth_line_found and profile.username and profile.password:
                    new_content_lines.append(f'auth-user-pass {auth_path}')

                # Write the new .conf file
                with open(conf_path, 'w') as f:
                    f.write('\n'.join(new_content_lines))
                os.chmod(conf_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH) # 644 permissions

                # Write the .auth file if credentials exist
                if profile.username and profile.password:
                    with open(auth_path, 'w') as f:
                        f.write(f"{profile.username}\n")
                        f.write(f"{profile.password}\n")
                    
                    # Set secure permissions (read/write for root only)
                    os.chmod(auth_path, stat.S_IRUSR | stat.S_IWUSR) # 600 permissions

                self.stdout.write(self.style.SUCCESS(f"Successfully synced profile '{profile.name}'."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to sync profile '{profile.name}': {e}"))

        self.stdout.write("VPN profile sync finished.")