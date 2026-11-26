import asyncio
import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Genera o rigenera il Podcast Audio per i Responsabili di Area tramite sintesi neurale."

    def handle(self, *args, **options):
        try:
            import edge_tts
        except ImportError:
            self.stderr.write("edge-tts non installato.")
            return

        from core.podcast_data import TEXT_PODCAST
        from core.podcast_dipendente_data import TEXT_PODCAST_DIPENDENTI

        dest_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'audio')
        os.makedirs(dest_dir, exist_ok=True)
        out_resp = os.path.join(dest_dir, 'podcast_responsabili_kandor.mp3')
        out_dip = os.path.join(dest_dir, 'podcast_dipendenti_telegram.mp3')

        async def _run():
            self.stdout.write(f"Sintesi vocale Podcast Responsabili...")
            comm1 = edge_tts.Communicate(TEXT_PODCAST, voice="it-IT-DiegoNeural", rate="+0%")
            await comm1.save(out_resp)

            self.stdout.write(f"Sintesi vocale Podcast Dipendenti...")
            comm2 = edge_tts.Communicate(TEXT_PODCAST_DIPENDENTI, voice="it-IT-DiegoNeural", rate="+0%")
            await comm2.save(out_dip)

        asyncio.run(_run())
        self.stdout.write(self.style.SUCCESS(f"Entrambi i podcast generati con successo!"))
