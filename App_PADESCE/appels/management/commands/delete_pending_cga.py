from django.core.management.base import BaseCommand
from App_PADESCE.appels.models import AppelCGA

class Command(BaseCommand):
    help = 'Supprime tous les appels CGA en attente de la base de donnees.'

    def handle(self, *args, **options):
        self.stdout.write("Demarrage de la suppression des appels en attente...")
        
        # On compte avant
        count_before = AppelCGA.objects.filter(status='en_attente').count()
        
        if count_before == 0:
            self.stdout.write(self.style.SUCCESS("Aucun appel en attente trouve."))
            return

        # Suppression par lots pour eviter de bloquer la base trop longtemps
        total_deleted = 0
        qs = AppelCGA.objects.filter(status='en_attente')
        
        # On boucle tant qu'il en reste (Django delete() sur un gros queryset peut etre lourd)
        # Mais ici .delete() sur le queryset est le plus simple.
        deleted_info = qs.delete()
        total_deleted = deleted_info[0]

        self.stdout.write(self.style.SUCCESS(f"Suppression terminee : {total_deleted} appels supprimes."))
