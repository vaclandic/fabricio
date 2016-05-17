import json

import six

import fabricio

from . import Image


def with_image(image_attr):
    class _WithImage(type):
        def __init__(cls, *args):
            image = getattr(cls, image_attr, None)
            if image is not None and not isinstance(image, Image):
                setattr(cls, image_attr, Image(image))
            super(_WithImage, cls).__init__(cls)
    return _WithImage


@six.add_metaclass(with_image('image'))
class Container(object):

    image = None  # type: Image

    cmd = None

    user = None

    ports = None

    env = None

    volumes = None

    links = None

    hosts = None

    network = None

    restart_policy = None

    stop_signal = None

    def __init__(self, name, options=None):
        self.name = name
        self.options = options

    def __str__(self):
        return str(self.name)

    def fork(self, name, options=None):
        options = options or self.options
        return self.__class__(name=name, options=options)

    @property
    def info(self):
        command = 'docker inspect --type container {container}'
        info = fabricio.exec_command(command.format(container=self))
        return json.loads(info)[0]

    def delete(self, force=False, ignore_errors=False):
        command = 'docker rm {force}{container}'
        force = force and '--force ' or ''
        fabricio.exec_command(
            command.format(container=self, force=force),
            ignore_errors=ignore_errors,
        )

    def run(self, tag=None):
        self.__class__.image[tag].run(
            cmd=self.cmd,
            temporary=False,
            name=self.name,
            user=self.user,
            ports=self.ports,
            env=self.env,
            volumes=self.volumes,
            links=self.links,
            hosts=self.hosts,
            network=self.network,
            restart_policy=self.restart_policy,
            stop_signal=self.stop_signal,
            options=self.options,
        )

    def execute(self, cmd):
        command = 'docker exec --tty {container} {cmd}'
        return fabricio.exec_command(command.format(container=self, cmd=cmd))

    def start(self):
        command = 'docker start {container}'
        fabricio.exec_command(command.format(container=self))

    def stop(self, timeout=10):
        command = 'docker stop --time {timeout} {container}'
        fabricio.exec_command(command.format(container=self, timeout=timeout))

    def restart(self, timeout=10):
        command = 'docker restart --time {timeout} {container}'
        fabricio.exec_command(command.format(container=self, timeout=timeout))

    def rename(self, new_name):
        command = 'docker rename {container} {new_name}'
        fabricio.exec_command(command.format(container=self, new_name=new_name))
        self.name = new_name

    def signal(self, signal):
        command = 'docker kill --signal {signal} {container}'
        fabricio.exec_command(command.format(container=self, signal=signal))

    def update(self, force=False, tag=None):
        if not force:
            try:
                current_image_id = self.image.id
            except RuntimeError:  # current container not found
                pass
            else:
                new_image = self.__class__.image[tag]
                if current_image_id == new_image.id:
                    fabricio.log('No change detected, update skipped.')
                    return
        new_container = self.fork(name=self.name)
        obsolete_container = self.get_backup_container()
        try:
            obsolete_image = obsolete_container.image
        except RuntimeError:
            pass
        else:
            obsolete_container.delete()
            obsolete_image.delete(ignore_errors=True)
        try:
            self.rename(obsolete_container.name)
        except RuntimeError:
            pass
        else:
            self.stop()
        new_container.run(tag=tag)

    def revert(self):
        failed_image = self.image
        self.stop()
        self.delete()
        failed_image.delete(ignore_errors=True)
        backup_container = self.get_backup_container()
        backup_container.start()
        backup_container.rename(self.name)

    def get_backup_container(self):
        return self.fork(name='{container}_backup'.format(container=self))
