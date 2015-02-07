# -*- coding: utf-8 -*-
#
# This file is part of fsinf-certificate-authority (https://github.com/fsinf/certificate-authority).
#
# fsinf-certificate-authority is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# fsinf-certificate-authority is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# fsinf-certificate-authority.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import uuid

from datetime import datetime
from datetime import timedelta

from OpenSSL import crypto

from django.conf import settings
from django.db import models


class CertificateManager(models.Manager):

    def from_csr(self, csr, subjectAltNames=None, days=730, algorithm=None,
                 watchers=None):
        # get algorithm used to sign certificate
        if algorithm is None:
            algorithm = settings.DIGEST_ALGORITHM

        # get certificate information
        req = crypto.load_certificate_request(crypto.FILETYPE_PEM, csr)
        subject = req.get_subject()
        cn = dict(subject.get_components())['CN']

        # get issuer cert:
        issuerKey = crypto.load_privatekey(
            crypto.FILETYPE_PEM, open(settings.CA_KEY).read())
        issuerPub = crypto.load_certificate(
            crypto.FILETYPE_PEM, open(settings.CA_CRT).read())

        # compute notAfter info
        expires = datetime.today() + timedelta(days=days + 1)
        expires = expires.replace(hour=0, minute=0, second=0, microsecond=0)

        # create signed certificate
        cert = crypto.X509()
        cert.set_serial_number(uuid.uuid4().int)
        cert.set_notBefore(datetime.utcnow().strftime('%Y%m%d%H%M%SZ'))
        cert.set_notAfter(expires.strftime('%Y%m%d%H%M%SZ'))
        cert.set_issuer(issuerPub.get_subject())
        cert.set_subject(req.get_subject())
        cert.set_pubkey(req.get_pubkey())

        # collect any extension
        extensions = []

        # add subjectAltName if given:
        if subjectAltNames:
            subjData = ','.join(['DNS:%s' % n for n in subjectAltNames])
            ext = crypto.X509Extension('subjectAltName', 0, subjData)
            extensions.append(ext)

        cert.add_extensions(extensions)

        # finally sign the certificate:
        cert.sign(issuerKey, algorithm)

        # create database object
        obj = self.create(
            csr=csr,
            pub=crypto.dump_certificate(crypto.FILETYPE_PEM, cert),
            cn=cn,
            expires=expires,
        )

        # add watchers:
        if watchers:
            obj.watchers.add(*watchers)

        return obj
