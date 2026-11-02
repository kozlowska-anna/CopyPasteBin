Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import {detectExtensionChannelState} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/extension-channel.js';

if (ARGV.length !== 2)
    throw new Error('expected system and user extension paths');

print(detectExtensionChannelState({
    systemPath: ARGV[0],
    userPath: ARGV[1],
}).status);
