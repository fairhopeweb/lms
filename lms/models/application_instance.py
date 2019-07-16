import secrets
from datetime import datetime
from Crypto.Cipher import AES
from Crypto import Random

import sqlalchemy as sa
from lms.db import BASE


class ApplicationInstance(BASE):
    """Class to represent a single lms install."""

    __tablename__ = "application_instances"

    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
    consumer_key = sa.Column(sa.String, unique=True, nullable=False)
    shared_secret = sa.Column(sa.String, nullable=False)
    lms_url = sa.Column(sa.String(2048), nullable=False)
    requesters_email = sa.Column(sa.String(2048), nullable=False)
    created = sa.Column(sa.TIMESTAMP, default=datetime.utcnow(), nullable=False)
    developer_key = sa.Column(sa.String)
    developer_secret = sa.Column(sa.LargeBinary)
    aes_cipher_iv = sa.Column(sa.LargeBinary)
    provisioning = sa.Column(
        sa.Boolean(),
        default=True,
        server_default=sa.sql.expression.true(),
        nullable=False,
    )

    #: A list of all the OAuth2Tokens for this application instance
    #: (each token belongs to a different user of this application
    #: instance's LMS).
    access_tokens = sa.orm.relationship(
        "OAuth2Token", back_populates="application_instance"
    )


def build_from_lms_url(
    lms_url, email, developer_key, developer_secret, encryption_key=None
):
    """Instantiate ApplicationInstance with lms_url."""
    encrypted_secret = developer_secret
    aes_iv = None
    if encryption_key is not None and developer_secret and developer_key:
        aes_iv = _build_aes_iv()
        encrypted_secret = _encrypt_oauth_secret(
            developer_secret, encryption_key, aes_iv
        )

    return ApplicationInstance(
        consumer_key=_build_unique_key(),
        shared_secret=_build_shared_secret(),
        lms_url=lms_url,
        requesters_email=email,
        developer_key=developer_key,
        developer_secret=encrypted_secret,
        aes_cipher_iv=aes_iv,
        created=datetime.utcnow(),
    )


def _build_aes_iv():
    """Build a 16 byte initialization vector."""
    return Random.new().read(AES.block_size)


def _build_shared_secret():
    """Generate a shared secret."""
    return secrets.token_hex(32)


def _build_unique_key():
    """Use the key base to generate lms key."""
    return "Hypothesis" + secrets.token_hex(16)


def _encrypt_oauth_secret(oauth_secret, key, init_v):
    """Encrypt an oauth secrety via AES encryption."""
    cipher = AES.new(key, AES.MODE_CFB, init_v)
    return cipher.encrypt(oauth_secret)
