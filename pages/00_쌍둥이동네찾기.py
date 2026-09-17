from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# 1. Streamlit 페이지 설정
# =========================================================
st.set_page_config(
    page_title="전국 인구구조 유사 지역 분석",
    page_icon="👥",
    layout="wide"
)

st.title("전국 인구구조 유사 지역 분석")

st.markdown(
    """
    원하는 지역을 선택하면 해당 지역의 연령별 인구구조를 확인하고,
    전국에서 **인구구조가 가장 비슷한 지역 TOP 5**를 찾을 수 있습니다.

    인구구조 유사성은 단순한 총인구가 아니라
    **0세~100세 이상 연령별 인구 비율의 분포**를 기준으로 계산합니다.
    """
)


# =========================================================
# 2. 현재 app.py 위치 확인
# =========================================================
BASE_DIR = Path(__file__).resolve().parent


# =========================================================
# 3. 한글 파일명 정규화 함수
# =========================================================
def normalize_filename(text):
    """
    macOS와 Linux 사이에서 발생할 수 있는
    한글 NFC/NFD 파일명 차이를 처리합니다.
    """
    return unicodedata.normalize(
        "NFC",
        str(text)
    )


# =========================================================
# 4. CSV 파일 자동 탐색
# =========================================================
def find_population_csv():
    """
    app.py가 있는 폴더와 하위 폴더에서
    CSV 파일을 자동으로 찾습니다.

    우선순위:
    1. 이름에 '연령별인구현황'이 들어간 CSV
    2. 이름에 '인구'가 들어간 CSV
    3. CSV가 하나뿐이면 그 파일
    """

    # 현재 폴더 + 하위 폴더까지 검색
    csv_files = list(
        BASE_DIR.rglob("*.csv")
    )

    # 숨김 폴더 / 가상환경 등 불필요한 경로 제외
    csv_files = [
        path
        for path in csv_files
        if ".git" not in path.parts
        and ".venv" not in path.parts
        and "venv" not in path.parts
        and "__pycache__" not in path.parts
    ]

    if len(csv_files) == 0:
        return None

    # -----------------------------------------
    # 1순위: 연령별인구현황
    # -----------------------------------------
    for path in csv_files:

        normalized_name = normalize_filename(
            path.name
        )

        if "연령별인구현황" in normalized_name:
            return path

    # -----------------------------------------
    # 2순위: 이름에 인구가 들어간 파일
    # -----------------------------------------
    for path in csv_files:

        normalized_name = normalize_filename(
            path.name
        )

        if "인구" in normalized_name:
            return path

    # -----------------------------------------
    # 3순위: CSV가 하나뿐이면 사용
    # -----------------------------------------
    if len(csv_files) == 1:
        return csv_files[0]

    # 여러 개라면 첫 번째 CSV 사용
    return csv_files[0]


# =========================================================
# 5. CSV 파일 읽기
# =========================================================
@st.cache_data
def load_data():

    file_path = find_population_csv()

    if file_path is None:
        raise FileNotFoundError(
            "GitHub 저장소에서 CSV 파일을 찾을 수 없습니다."
        )

    # 주민등록 인구 CSV에서 많이 사용되는 인코딩
    encodings = [
        "cp949",
        "utf-8-sig",
        "utf-8"
    ]

    last_error = None

    for encoding in encodings:

        try:

            data = pd.read_csv(
                file_path,
                encoding=encoding,
                low_memory=False
            )

            return data, str(file_path)

        except UnicodeDecodeError as e:
            last_error = e

    raise last_error


# =========================================================
# 6. 데이터 불러오기
# =========================================================
try:

    df, detected_file_path = load_data()

except FileNotFoundError:

    st.error(
        "CSV 데이터 파일을 찾을 수 없습니다."
    )

    st.markdown(
        """
        GitHub 저장소에 CSV 파일이 실제로 업로드되어 있는지 확인하세요.

        예:
        ```text
        저장소/
        ├── app.py
        ├── requirements.txt
        └── 연령별인구현황.csv
        ```
        """
    )

    st.write(
        "Streamlit이 현재 확인하고 있는 폴더:"
    )

    st.code(
        str(BASE_DIR)
    )

    st.write(
        "현재 폴더의 파일:"
    )

    for path in BASE_DIR.iterdir():
        st.write(f"- {path.name}")

    st.stop()


except Exception as e:

    st.error(
        "CSV 파일을 읽는 중 오류가 발생했습니다."
    )

    st.exception(e)

    st.stop()


# =========================================================
# 7. 데이터 파일 확인
# =========================================================
st.success(
    f"데이터 파일을 정상적으로 불러왔습니다: "
    f"{Path(detected_file_path).name}"
)


# =========================================================
# 8. 숫자 변환 함수
# =========================================================
def clean_number(value):

    if pd.isna(value):
        return 0

    value = (
        str(value)
        .replace(",", "")
        .strip()
    )

    if value == "":
        return 0

    try:
        return int(float(value))

    except (ValueError, TypeError):
        return 0


# =========================================================
# 9. 행정구역 열 확인
# =========================================================
if "행정구역" not in df.columns:

    st.error(
        """
        CSV 파일은 읽었지만 '행정구역' 열을 찾지 못했습니다.

        올바른 주민등록 연령별 인구현황 파일인지 확인하세요.
        """
    )

    st.write(
        "현재 CSV에서 확인된 열:"
    )

    st.write(
        df.columns.tolist()
    )

    st.stop()


# =========================================================
# 10. 전체 연령별 열 찾기
# =========================================================
def find_age_columns(dataframe):

    age_columns = []

    pattern = re.compile(
        r"^\d{4}년\d{2}월_계_(\d+세|100세 이상)$"
    )

    for column in dataframe.columns:

        match = pattern.match(
            str(column)
        )

        if match is None:
            continue

        age_label = match.group(1)

        if age_label == "100세 이상":

            age = 100

        else:

            age = int(
                age_label.replace(
                    "세",
                    ""
                )
            )

        age_columns.append(
            {
                "age": age,
                "label": age_label,
                "column": column
            }
        )

    age_columns.sort(
        key=lambda x: x["age"]
    )

    return age_columns


# =========================================================
# 11. 지역명 정리
# =========================================================
df["지역명"] = (
    df["행정구역"]
    .astype(str)
    .str.replace(
        r"\s*\(\d+\)\s*$",
        "",
        regex=True
    )
    .str.strip()
)


# =========================================================
# 12. 행정구역 코드 추출
# =========================================================
df["행정구역코드"] = (
    df["행정구역"]
    .astype(str)
    .str.extract(
        r"\((\d+)\)"
    )[0]
)


# =========================================================
# 13. 기준 연월 확인
# =========================================================
year_month = None

for column in df.columns:

    match = re.match(
        r"^(\d{4})년(\d{2})월_",
        str(column)
    )

    if match:

        year = match.group(1)
        month = match.group(2)

        year_month = (
            f"{year}년 {month}월"
        )

        break


if year_month:

    st.caption(
        f"주민등록 인구통계 기준: {year_month}"
    )


# =========================================================
# 14. 연령별 열 찾기
# =========================================================
age_columns = find_age_columns(
    df
)


if len(age_columns) == 0:

    st.error(
        """
        0세~100세 이상의 연령별 인구 열을 찾지 못했습니다.

        CSV 파일 형식을 확인하세요.
        """
    )

    st.stop()


age_column_names = [
    item["column"]
    for item in age_columns
]


age_values = np.array(
    [
        item["age"]
        for item in age_columns
    ]
)


age_labels = [
    item["label"]
    for item in age_columns
]


# =========================================================
# 15. 전국 연령별 인구 데이터 숫자로 변환
# =========================================================
@st.cache_data
def prepare_population_data(
    dataframe,
    columns
):

    population_data = (
        dataframe[columns]
        .copy()
    )

    for column in columns:

        population_data[column] = (
            population_data[column]
            .astype(str)
            .str.replace(
                ",",
                "",
                regex=False
            )
            .str.strip()
        )

        population_data[column] = (
            pd.to_numeric(
                population_data[column],
                errors="coerce"
            )
            .fillna(0)
        )

    return population_data


population_df = prepare_population_data(
    df,
    age_column_names
)


# =========================================================
# 16. 각 지역 총인구 계산
# =========================================================
region_total_population = (
    population_df.sum(
        axis=1
    )
)


# =========================================================
# 17. 연령별 인구 비율 계산
# =========================================================
population_share = (
    population_df
    .div(
        region_total_population.replace(
            0,
            np.nan
        ),
        axis=0
    )
    .fillna(0)
)


# =========================================================
# 18. 코사인 유사도 계산용 행렬 준비
# =========================================================
population_matrix = (
    population_share
    .to_numpy(
        dtype=float
    )
)


vector_norms = np.linalg.norm(
    population_matrix,
    axis=1,
    keepdims=True
)


normalized_population_matrix = np.divide(
    population_matrix,
    vector_norms,
    out=np.zeros_like(
        population_matrix
    ),
    where=vector_norms != 0
)


# =========================================================
# 19. 유사 지역 TOP N 함수
# =========================================================
def find_similar_regions(
    selected_index,
    top_n=5
):

    selected_position = df.index.get_loc(
        selected_index
    )

    selected_vector = (
        normalized_population_matrix[
            selected_position
        ]
    )

    similarities = (
        normalized_population_matrix
        @ selected_vector
    )


    result = pd.DataFrame(
        {
            "원본인덱스": df.index,
            "지역명": df["지역명"].values,
            "행정구역코드": df["행정구역코드"].values,
            "총인구": region_total_population.values,
            "유사도": similarities
        }
    )


    # 선택 지역 자신 제거
    result = result[
        result["원본인덱스"]
        != selected_index
    ]


    # 인구 0인 지역 제거
    result = result[
        result["총인구"] > 0
    ]


    result = (
        result
        .sort_values(
            "유사도",
            ascending=False
        )
        .head(top_n)
        .copy()
    )


    result["유사도(%)"] = (
        result["유사도"]
        * 100
    )


    return result


# =========================================================
# 20. 지역 선택
# =========================================================
st.divider()

st.subheader(
    "분석할 지역 선택"
)


search_keyword = st.text_input(
    "지역명을 입력하세요",
    placeholder=(
        "예: 서울, 강남구, 종로구, "
        "청운효자동, 수원시"
    )
)


search_keyword = (
    search_keyword.strip()
)


# =========================================================
# 21. 검색 결과 필터링
# =========================================================
if search_keyword:

    filtered_df = df[
        df["지역명"]
        .str.contains(
            search_keyword,
            case=False,
            na=False,
            regex=False
        )
    ]

else:

    filtered_df = df


# =========================================================
# 22. 지역 선택 옵션
# =========================================================
region_options = (
    filtered_df[
        [
            "지역명",
            "행정구역코드"
        ]
    ]
    .copy()
)


region_options["행정구역코드"] = (
    region_options[
        "행정구역코드"
    ]
    .fillna("")
    .astype(str)
)


region_options["선택표시"] = (
    region_options["지역명"]
    + " ("
    + region_options["행정구역코드"]
    + ")"
)


region_options = (
    region_options
    .drop_duplicates(
        subset=["선택표시"]
    )
)


if region_options.empty:

    st.warning(
        f"'{search_keyword}'에 해당하는 지역을 찾을 수 없습니다."
    )

    st.stop()


selected_display = st.selectbox(
    "지역을 선택하세요",
    options=region_options[
        "선택표시"
    ].tolist()
)


# =========================================================
# 23. 선택 지역 확인
# =========================================================
selected_option = (
    region_options[
        region_options["선택표시"]
        == selected_display
    ]
    .iloc[0]
)


selected_region = (
    selected_option["지역명"]
)


selected_code = str(
    selected_option[
        "행정구역코드"
    ]
)


selected_mask = (
    (df["지역명"] == selected_region)
    &
    (
        df["행정구역코드"]
        .fillna("")
        .astype(str)
        == selected_code
    )
)


selected_rows = df[
    selected_mask
]


if selected_rows.empty:

    st
