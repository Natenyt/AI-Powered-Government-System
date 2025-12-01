from django.urls import path
from .views import MessagePrecheckView

urlpatterns = [
    path('precheck/', MessagePrecheckView.as_view(), name='message_precheck'),
]
