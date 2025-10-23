import dataclasses
import json
import base64
from typing import Type, TypeVar, Dict, Any

# Define a type variable for generic class methods
T = TypeVar('T', bound='BaseMessage')

class BaseMessage:
    """Base class for all Chorus federation messages."""

    def to_dict(self) -> Dict[str, Any]:
        """Converts the message to a dictionary, handling bytes fields."""
        data = dataclasses.asdict(self)
        for key, value in data.items():
            if isinstance(value, bytes):
                data[key] = base64.b64encode(value).decode('utf-8')
            elif isinstance(value, BaseMessage):
                data[key] = value.to_dict()
        return data

    def to_bytes(self) -> bytes:
        """Serializes the message to bytes using JSON and base64 for bytes fields."""
        return json.dumps(self.to_dict()).encode('utf-8')

    @classmethod
    def from_bytes(cls: Type[T], data: bytes) -> T:
        """Deserializes the message from bytes, handling base64 decoding for bytes fields."""
        decoded_data = json.loads(data.decode('utf-8'))
        return cls.from_dict(decoded_data)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Creates a message instance from a dictionary, handling base64 decoding for bytes fields."""
        # Create a copy to avoid modifying the original dictionary during iteration
        processed_data = data.copy()
        for field in dataclasses.fields(cls):
            if field.name in processed_data:
                value = processed_data[field.name]
                if field.type == bytes and isinstance(value, str):
                    processed_data[field.name] = base64.b64decode(value.encode('utf-8'))
                elif issubclass(field.type, BaseMessage) and isinstance(value, dict):
                    processed_data[field.name] = field.type.from_dict(value)
        return cls(**processed_data)

@dataclasses.dataclass
class PostAnnouncement(BaseMessage):
    post_id: bytes
    author_pubkey: bytes
    content_hash: bytes
    order_index: int
    creation_day: int

@dataclasses.dataclass
class UserRegistration(BaseMessage):
    user_pubkey: bytes
    registration_day: int
    day_proof_hash: bytes

@dataclasses.dataclass
class DayProof(BaseMessage):
    day_number: int
    canonical_proof_hash: bytes
    validator_quorum_sig: bytes

@dataclasses.dataclass
class ModerationEvent(BaseMessage):
    target_ref: bytes
    action: str
    reason_hash: bytes
    creation_day: int

@dataclasses.dataclass
class InstanceJoinRequest(BaseMessage):
    instance_id: str
    instance_pubkey: bytes
    contact_info: str
    timestamp: int

@dataclasses.dataclass
class FederationEnvelope(BaseMessage):
    sender_instance: str
    timestamp: int
    message_type: str
    message_data: bytes  # This will hold serialized bytes of other message types
    signature: bytes

    def get_message_data_object(self) -> BaseMessage:
        """Deserializes message_data into the appropriate message object."""
        message_type_map = {
            "PostAnnouncement": PostAnnouncement,
            "UserRegistration": UserRegistration,
            "DayProof": DayProof,
            "ModerationEvent": ModerationEvent,
            "InstanceJoinRequest": InstanceJoinRequest,
        }
        message_cls = message_type_map.get(self.message_type)
        if not message_cls:
            raise ValueError(f"Unknown message_type: {self.message_type}")
        return message_cls.from_bytes(self.message_data)

    def set_message_data_object(self, message_object: BaseMessage):
        """Serializes a message object and sets it as message_data."""
        self.message_data = message_object.to_bytes()
        self.message_type = message_object.__class__.__name__
