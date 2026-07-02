from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message
from aiogram_dialog import Dialog, DialogManager
from aiogram_dialog.api.protocols import CancelEventProcessing


class QuietDialog(Dialog):
    async def _message_handler(self, message: Message, dialog_manager: DialogManager):
        old_context = dialog_manager.current_context()
        window = await self._current_window(dialog_manager)
        try:
            processed = await window.process_message(message, self, dialog_manager)
        except CancelEventProcessing:
            processed = False
        if not processed and getattr(window, 'on_message', None) is None:
            raise SkipHandler
        if self._need_refresh(processed, old_context, dialog_manager):
            await dialog_manager.show()
