import i18next from 'i18next'

export function getLocalizedString(string: string | Record<string, string>): string {
    if (typeof string === 'string') return string;
    return string[i18next.language] || Object.values(string)[0] || "";
}

export function warningTooltipText(warnings?: { message?: string }[]): string {
    return (warnings ?? []).map((warning) => warning.message).filter((message): message is string => Boolean(message)).join('\n');
}
