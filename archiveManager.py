import os
import re
import shutil


def extractYearMonthFromFilename(filename):
    """
    Try to extract a yyyymm string from a video filename.
    Supports patterns like: 20240115, 2024-01-15, 2024_01_15, 2024-01, 2024_01
    Returns 'yyyymm' string, or None if no date pattern is found.
    """
    fullDatePattern = r'(20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])'
    yearMonthPattern = r'(20\d{2})[-_](0[1-9]|1[0-2])'

    match = re.search(fullDatePattern, filename)
    if match:
        yyyymm = f"{match.group(1)}{match.group(2)}"
        print(f"[extractYearMonthFromFilename] {filename} -> {yyyymm} (full date match)")
        return yyyymm

    match = re.search(yearMonthPattern, filename)
    if match:
        yyyymm = f"{match.group(1)}{match.group(2)}"
        print(f"[extractYearMonthFromFilename] {filename} -> {yyyymm} (year-month match)")
        return yyyymm

    print(f"[extractYearMonthFromFilename] {filename} -> no date found")
    return None


def getArchiveTargetDir(archiveRoot, filename):
    yyyymm = extractYearMonthFromFilename(filename)
    subDirName = yyyymm if yyyymm else 'UnknownDate'
    targetDir = os.path.join(archiveRoot, subDirName)
    os.makedirs(targetDir, exist_ok=True)
    return targetDir


def archiveMarkedFiles(dataDir, archiveRoot, filenames):
    """
    Move mp4 + its json (marker file) for each given filename into the
    archive directory, grouped by yyyymm parsed from the filename
    (or 'UnknownDate' if no date can be parsed).

    filenames: list of mp4 basenames that are expected to already have a
               completed marker json (caller decides eligibility).

    Returns dict: { archivedCount, archivedFiles, errors }
    """
    os.makedirs(archiveRoot, exist_ok=True)

    archivedCount = 0
    archivedFiles = []
    errors = []

    print(f"[archiveMarkedFiles] start, candidates={len(filenames)} archiveRoot={archiveRoot}")

    for name in filenames:
        safeName = os.path.basename(name)
        srcMp4 = os.path.join(dataDir, safeName)
        jsonName = os.path.splitext(safeName)[0] + '.json'
        srcJson = os.path.join(dataDir, jsonName)

        if not os.path.exists(srcMp4):
            print(f"[archiveMarkedFiles] skip, mp4 missing: {safeName}")
            errors.append(f"{safeName}: video file not found")
            continue

        if not os.path.exists(srcJson):
            print(f"[archiveMarkedFiles] skip, no marker json (not marked): {safeName}")
            errors.append(f"{safeName}: marker json not found, skipped")
            continue

        targetDir = getArchiveTargetDir(archiveRoot, safeName)
        dstMp4 = os.path.join(targetDir, safeName)
        dstJson = os.path.join(targetDir, jsonName)

        if os.path.exists(dstMp4) or os.path.exists(dstJson):
            print(f"[archiveMarkedFiles] skip, target already exists: {safeName} -> {targetDir}")
            errors.append(f"{safeName}: already exists in archive target, skipped")
            continue

        try:
            shutil.move(srcMp4, dstMp4)
            shutil.move(srcJson, dstJson)
            archivedCount += 1
            archivedFiles.append(safeName)
            print(f"[archiveMarkedFiles] archived: {safeName} -> {targetDir}")
        except Exception as e:
            print(f"[archiveMarkedFiles] error archiving {safeName}: {e}")
            errors.append(f"{safeName}: {str(e)}")

    print(f"[archiveMarkedFiles] finished: archivedCount={archivedCount} errorCount={len(errors)}")

    return {
        'archivedCount': archivedCount,
        'archivedFiles': archivedFiles,
        'errors': errors
    }
