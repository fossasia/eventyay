from re import search


def getPemContent(pem, template):
    pattern = template.format(content="(.*)")
    return search("".join(pattern.splitlines()), "".join(pem.splitlines())).group(1)


def createPem(content, template):
    lines = [
        content[start:start + 64]
        for start in range(0, len(content), 64)
    ]
    return template.format(content="\n".join(lines))
