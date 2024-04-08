import {toast, ToastPosition } from 'react-toastify';

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

function showToast(message:string | any, type:string, toastId:string, position:ToastPosition=toast.POSITION.BOTTOM_CENTER, autoCloseTime:number|false=5000) {
    if (autoCloseTime === -1)
      autoCloseTime = false
    if(type === "success") {
        toast.success(message, {
            position: position,
            autoClose: autoCloseTime,
            closeOnClick: false,
            toastId: toastId
        });
    } else if (type === "error") {
        toast.error(message, {
            position: position,
            autoClose: autoCloseTime,
            closeOnClick: false,
            toastId: toastId
        });
    } else if (type === "info") {
        toast.info(message, {
            position: position,
            autoClose: autoCloseTime,
            closeOnClick: false,
            toastId: toastId
        });
    } else if (type === "warning") {
        toast.warning(message, {
            position: position,
            autoClose: autoCloseTime,
            closeOnClick: false,
            toastId: toastId
        });
    } else {
        toast(message, {
            position: position,
            autoClose: autoCloseTime,
            closeOnClick: false,
            toastId: toastId
        });
    }
}

async function copyProfileUrlToClipboard(userId:string) {
    const url:string = window.location.origin + "/profile/" + userId;
    try {
      await navigator.clipboard.writeText(url);
      showToast("Profile URL copied to clipboard!", "success", "profile-url-copied");
    } catch (err) {
      showToast("Error while copying profile URL to clipboard", "error", "profile-url-copied-error");
    }
}


function getIdFromURL(url:string) {
    // Detect UUID in an url.
    // Initial slash: \/
    // Eight hex characters: [\da-f]{8}
    // Three groups of hyphen and four hex characters: (?:-[\da-f]{4})
    // Hyphen and twelve hex charactersL: -[\da-f]{12}
    // Optional forward slash at the end: \/?
    return url.match(/\/([\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12})\/?/)?.[1] ?? "";
};

function parseLinks(text:string) {
    const pattern = /(https?:\/\/[^\s]+)/g; // Regular expression to match URLs
  
    const parts = text.split(pattern); // Split the text into parts using the pattern
  
    return parts.map((part, index) => {
      if (pattern.test(part)) {
        // If the part matches the pattern, it's a link
        return (
          <a key={index} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        );
      } else {
        // Otherwise, it's regular text
        return <span key={index}>{part}</span>;
      }
    });
  }

function isUUID(uuid:string) {
  const isMatched = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(uuid);
  return isMatched;
}

export { humanFileSize, showToast, copyProfileUrlToClipboard, getIdFromURL, parseLinks, isUUID };