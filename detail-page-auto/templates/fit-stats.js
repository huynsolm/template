document.fonts.ready.then(() => {
                    for (const value of document.querySelectorAll('.stat-list dd')) {
                        const initial = parseFloat(getComputedStyle(value).fontSize);
                        const minimum = parseFloat(getComputedStyle(value).getPropertyValue('--fit-min')) || 1;
                        for (let size = initial; size >= minimum; size -= 2) {
                            value.style.fontSize = size + 'px';
                            if (value.scrollWidth <= value.clientWidth) break;
                        }
                        if (minimum > 1 && value.scrollWidth > value.clientWidth) {
                            value.style.whiteSpace = 'normal';
                            value.style.overflowWrap = 'anywhere';
                        }
                    }
                });
