import {toast } from 'react-toastify';

/**
 * THIS FUNCTION CREDIT TO https://stackoverflow.com/questions/10420352/converting-file-size-in-bytes-to-human-readable-string/10420404
 * 
 * Format bytes as human-readable text.
 * 
 * @param bytes Number of bytes.
 * @param si True to use metric (SI) units, aka powers of 1000. False to use 
 *           binary (IEC), aka powers of 1024.
 * @param dp Number of decimal places to display.
 * 
 * @return Formatted string.
 */
function humanFileSize(bytes: number, si: boolean = true, dp: number = 1) {
    const thresh = si ? 1000 : 1024;

    if (Math.abs(bytes) < thresh) {
        return bytes + ' B';
    }

    const units = si
        ? ['kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
        : ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
    let u = -1;
    const r = 10 ** dp;

    do {
        bytes /= thresh;
        ++u;
    } while (Math.round(Math.abs(bytes) * r) / r >= thresh && u < units.length - 1);

    if (bytes.toFixed(dp).length > 4) {
        bytes /= thresh;
        ++u;
    }


    return bytes.toFixed(dp) + ' ' + units[u];
}

function showToast(message:string, type:string, position=toast.POSITION.BOTTOM_CENTER) {

    if(type === "success") {
        toast.success(message, {
            position: position
        });
    } else if (type == "error") {
        toast.error(message, {
            position: position
        });
    } else if (type == "info") {
        toast.info(message, {
            position: position
        });
    } else if (type == "warning") {
        toast.warning(message, {
            position: position
        });
    } else {
        toast(message, {
            position: position
        });
    }
}

async function copyProfileUrlToClipboard(userId:string) {
    const url:string = window.location.origin + "/profile/" + userId;
    try {
      await navigator.clipboard.writeText(url);
      showToast("Profile URL copied to clipboard!", "success");
    } catch (err) {
      showToast("Error while copying profile URL to clipboard", "error");
    }
}

export { humanFileSize, showToast, copyProfileUrlToClipboard };