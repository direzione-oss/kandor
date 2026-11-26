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

        dest_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'audio')
        os.makedirs(dest_dir, exist_ok=True)
        out_file = os.path.join(dest_dir, 'podcast_responsabili_kandor.mp3')

        self.stdout.write(f"Avvio sintesi neurale podcast su {out_file}...")

        async def _run():
            comm = edge_tts.Communicate(TEXT_PODCAST, voice="it-IT-DiegoNeural", rate="+0%")
            await comm.save(out_file)

        asyncio.run(_run())
        self.stdout.write(self.style.SUCCESS(f"Podcast generato con successo! ({os.path.getsize(out_file)} bytes)"))
