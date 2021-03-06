#! /usr/bin/env python

import argparse
import itertools
import re
from pathlib import Path

from bs4 import BeautifulSoup
import nltk


def set_up_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputdir', help="input directory containing hocr files")
    parser.add_argument("-o", "--output", help="output directory for the method section")
    return parser


def select_hocr_files(input_dir):
    path = Path(input_dir).expanduser()
    selection = path.glob('*.html')
    # Sort files by page number.
    hocr_files = sorted(selection,
                        key=lambda f:
                            int(''.join(filter(str.isdigit, f.stem))))
    return hocr_files


stopwords = nltk.corpus.stopwords.words('english')


def build_methods_regex():
    terms = ["Method", "METHOD", "Materials and Methods",
             "MATERIALS AND METHODS", "Materials methods",
             "Material and methods", "Materials and methods",
             "Study site and methods", "Study Area and Methods",
             "M E T H O D S", "Material and Methods", "STUDY SITE AND METHODS",
             "Materials and Methods", "Study area and methods",
             "STUDY AREA AND METHODS",
             "Study sites and methods", "MATERIAL AND METHODS",
             "MATERIALS AN D METHODS", "Sample sites and methods"]
    regex = re.compile(r'^([0-9]+.?\s*)?({})(.*)$'.format("|".join(terms)))
    return regex


def build_end_methods_regex():
    terms = ["Discussion", "DISCUSSION", "Conclusion", "Results", "RESULTS",
             "Resuﬂs", "Acknowledgements",
             "Appendix", "Appendices"]
    return re.compile(r'^([0-9]+.?\s*)?({})(.*)$'.format("|".join(terms)))


def build_literature_heading_regex():
    terms = ["References", "Bibliography", "Literature", "LITERATURE",
             "REFERENCES", "R E F E R E N C E S"]
    return re.compile(r'^([0-9]+.?\s*)?({})(.*)$'.format("|".join(terms)))


def soup_generator(hocr_files, start_page=0):
    for page_no, hocr_file in enumerate(hocr_files):
        if page_no < start_page:
            continue
        with open(hocr_file) as hocr:
            page_soup = BeautifulSoup(hocr.read(), 'html.parser')
            yield page_soup


def find_regex(hocr_files, regex):
    for page_no, page_soup in enumerate(soup_generator(hocr_files)):
        for area_no, area in enumerate(page_soup.find_all("div", "ocr_carea")):
            for line_no, line in enumerate(area.find_all("span", "ocr_line")):
                words = list(line.find_all("span", "ocrx_word"))
                line_text = " ".join(map(lambda e: e.text, words))
                match = regex.match(line_text)

                if match:
                    pre_match, match_str, post_match = match.groups()
                    # Check whether the whole line is text.
                    if len(post_match.split()) > 5 or\
                        post_match.count('.') >= 1 or\
                        "," in post_match:
                        # Skip the match if it occurs in plain text.
                        pass
                    else:
                        #print("Match {} found at page {} in area {} at line {}".
                        #      format(match, page_no, area_no, line_no))
                        return page_no, area_no, line_no

    if not hocr_files:
        raise RuntimeError("Directory is empty")

    hocr_collection = hocr_files[0].parent
    raise RuntimeError(
        "Cannot find regex={} section in {}".format(regex, hocr_collection))


def find_method_section(hocr_files):
    method_regex = build_methods_regex()
    return find_regex(hocr_files, method_regex)


def find_method_end(hocr_files):
    method_end_regex = build_end_methods_regex()
    return find_regex(hocr_files, method_end_regex)


def areas_to_text(page_soup, start=None, end=None):
    areas = page_soup.find_all("div", "ocr_carea")
    text_areas = []

    for area in itertools.islice(areas, start, end):
        if area.has_attr("ts:type"):
            if area['ts:type'] in ['decoration', 'line', 'caption']:
                continue
            elif int(area['ts:table-score']) > 4:
                continue
        for line in area.find_all("span", "ocr_line"):
            words = list(line.find_all("span", "ocrx_word"))
            line_text = " ".join(map(lambda e: e.text, words))
            text_areas.append(line_text)

    return '\n'.join(text_areas)


def collect_methods_text(hocr_files, start_tuple, end_tuple):
    page_no_method_start, area_no_start, line_no_start = start_tuple
    page_no_method_end, area_no_end, line_no_end = end_tuple

    soups = list(soup_generator(hocr_files))

    if page_no_method_start == page_no_method_end:
        # Method start and end are on the same page.
        # Slice this page accordingly.
        methods_text = areas_to_text(soups[page_no_method_start],
                                     area_no_start, area_no_end)
        return methods_text

    # Otherwise methods text stretches multiple pages.
    methods_text = []

    # Handle start of the method section
    text_first_page = areas_to_text(soups[page_no_method_start],
                                    start=area_no_start)
    methods_text.append(text_first_page)

    # Compose entire pages between start and end of the method's section.
    for soup in itertools.islice(soups,
                                 page_no_method_start + 1,
                                 page_no_method_end):
        page_text = areas_to_text(soup)
        methods_text.append(page_text)
        # TODO Skip non-textual content.

    # Compose text from last page of the methods section.
    text_last_page = areas_to_text(soups[page_no_method_end],
                                   start=None,
                                   end=area_no_end + 1)
    methods_text.append(text_last_page)

    return '\n'.join(methods_text)


def generate_file_from_input_dir(input_dir):
    path_tesseract = Path(input_dir)
    path_to_paper = path_tesseract.parent
    paper_name = path_to_paper.stem
    return f"{paper_name}_methods.txt"


def write_methods_section_to_file(file_name, methods_text):
    out_path = Path(OUT_DIR)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / file_name
    print(file_path)
    file_path.touch()
    file_path.write_text(methods_text)
    return


OUT_DIR = "./output"


def main():
    parser = set_up_argparser()
    args = parser.parse_args()
    print(args.inputdir)
    hocr_files = select_hocr_files(args.inputdir)

    start_method_tuple = find_method_section(hocr_files)
    end_method_tuple = find_method_end(hocr_files)

    method_text = collect_methods_text(hocr_files, start_method_tuple, end_method_tuple)
    global OUT_DIR
    if args.output:
        OUT_DIR = args.output

    print(OUT_DIR)
    print(method_text)
    file_name = generate_file_from_input_dir(args.inputdir)
    write_methods_section_to_file(file_name, method_text)


if __name__ == "__main__":
    main()
