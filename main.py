import os
import re
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# 1. Streamlit 페이지 설정
# =========================================================
st.set_page_config(
    page_title="지역별 인구구조 분석",
    page_icon="👥",
    layout="wide"
)


st.title("지역별 연령 인구구조 분석")

st.markdown(
    """
    지역명을 검색하고 원하는 지역을 선택하면
    해당 지역의 **연령별 전체·남성·여성 인구 구조**를 확인할 수 있습니다.
    """
)


# =========================================================
# 2. 데이터 파일명
# =========================================================
TARGET_FILE_NAME = "202608_202608_연령별인구현황_월간.csv"


# =========================================================
# 3. app.py가 위치한 폴더 확인
# =========================================================
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# =========================================================
# 4. CSV 파일 찾기
# =========================================================
def find_data_file():
    """
    app.py와 같은 폴더에서 지정한 CSV 파일을 찾습니다.

    Mac에서 한글 파일명이 NFC/NFD 방식으로 다르게 저장되는
    문제를 방지하기 위해 Unicode 정규화를 적용합니다.
    """

    target_normalized = unicodedata.normalize(
        "NFC",
        TARGET_FILE_NAME
    )

    for file_name in os.listdir(BASE_DIR):

        file_normalized = unicodedata.normalize(
            "NFC",
            file_name
        )

        if file_normalized == target_normalized:

            return os.path.join(
                BASE_DIR,
                file_name
            )

    return None


# =========================================================
# 5. CSV 데이터 불러오기
# =========================================================
@st.cache_data
def load_data():

    file_path = find_data_file()

    if file_path is None:

        raise FileNotFoundError(
            f"{TARGET_FILE_NAME} 파일을 찾을 수 없습니다."
        )

    # 현재 행정안전부 CSV는 cp949 인코딩
    try:

        df = pd.read_csv(
            file_path,
            encoding="cp949",
            low_memory=False
        )

        return df

    except UnicodeDecodeError:

        pass


    # 혹시 utf-8-sig로 저장된 경우
    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
            low_memory=False
        )

        return df

    except UnicodeDecodeError:

        pass


    # 마지막으로 utf-8 시도
    df = pd.read_csv(
        file_path,
        encoding="utf-8",
        low_memory=False
    )

    return df


# =========================================================
# 6. 데이터 로딩
# =========================================================
try:

    df = load_data()


except FileNotFoundError as e:

    st.error(str(e))

    st.warning(
        """
        app.py와 CSV 파일이 GitHub 저장소의 같은 폴더에 있는지 확인하세요.
        """
    )

    st.subheader("현재 확인된 파일")

    files = os.listdir(BASE_DIR)

    for file in files:
        st.write(f"- {file}")

    st.stop()


except Exception as e:

    st.error(
        f"데이터 파일을 읽는 중 오류가 발생했습니다.\n\n{e}"
    )

    st.stop()


# =========================================================
# 7. 숫자 변환 함수
# =========================================================
def clean_number(value):
    """
    문자열 숫자를 정수로 변환합니다.

    예:
    '9,281,625' -> 9281625
    """

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
# 8. 연령 열 찾기
# =========================================================
def find_age_columns(dataframe, gender):
    """
    gender

    계 = 전체
    남 = 남성
    여 = 여성

    예:
    2026년08월_계_0세
    2026년08월_남_35세
    2026년08월_여_100세 이상
    """

    age_columns = []

    pattern = re.compile(
        rf"^\d{{4}}년\d{{2}}월_{gender}_(\d+세|100세 이상)$"
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
# 9. 필수 열 확인
# =========================================================
if "행정구역" not in df.columns:

    st.error(
        """
        데이터에서 '행정구역' 열을 찾을 수 없습니다.

        올바른 연령별 인구현황 CSV 파일인지 확인하세요.
        """
    )

    st.stop()


# =========================================================
# 10. 지역명 정리
# =========================================================
# 원본
# 서울특별시 종로구 (1111000000)
#
# 화면 표시
# 서울특별시 종로구

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
# 11. 기준 연월 확인
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
# 12. 연령별 열 찾기
# =========================================================
total_age_columns = find_age_columns(
    df,
    "계"
)

male_age_columns = find_age_columns(
    df,
    "남"
)

female_age_columns = find_age_columns(
    df,
    "여"
)


if len(total_age_columns) == 0:

    st.error(
        """
        전체 연령별 인구 데이터를 찾을 수 없습니다.

        CSV의 열 이름을 확인하세요.
        """
    )

    st.stop()


# =========================================================
# 13. 남녀 열을 연령 기준으로 딕셔너리화
# =========================================================
male_column_dict = {
    item["age"]: item["column"]
    for item in male_age_columns
}


female_column_dict = {
    item["age"]: item["column"]
    for item in female_age_columns
}


# =========================================================
# 14. 지역 검색
# =========================================================
st.divider()

st.subheader("지역 선택")


search_keyword = st.text_input(
    "지역명을 입력하세요",
    placeholder="예: 서울, 종로구, 강남구, 수원시"
)


# 검색어 양쪽 공백 제거
search_keyword = search_keyword.strip()


# =========================================================
# 15. 검색 결과 필터링
# =========================================================
if search_keyword:

    filtered_df = df[
        df["지역명"].str.contains(
            search_keyword,
            case=False,
            na=False,
            regex=False
        )
    ]

else:

    filtered_df = df


region_options = (
    filtered_df["지역명"]
    .dropna()
    .drop_duplicates()
    .tolist()
)


# =========================================================
# 16. 검색 결과가 없는 경우
# =========================================================
if len(region_options) == 0:

    st.warning(
        f"'{search_keyword}'에 해당하는 지역을 찾을 수 없습니다."
    )

    st.stop()


# =========================================================
# 17. 지역 선택
# =========================================================
selected_region = st.selectbox(
    "지역을 선택하세요",
    options=region_options
)


# =========================================================
# 18. 선택 지역 데이터 추출
# =========================================================
selected_rows = df[
    df["지역명"] == selected_region
]


if selected_rows.empty:

    st.error(
        "선택한 지역의 데이터를 찾을 수 없습니다."
    )

    st.stop()


selected_row = selected_rows.iloc[0]


# =========================================================
# 19. 연령별 데이터 만들기
# =========================================================
age_data = []


for item in total_age_columns:

    age = item["age"]

    age_label = item["label"]

    total_column = item["column"]


    total_population_age = clean_number(
        selected_row[total_column]
    )


    # 남성
    male_column = male_column_dict.get(
        age
    )

    if male_column is not None:

        male_population_age = clean_number(
            selected_row[male_column]
        )

    else:

        male_population_age = 0


    # 여성
    female_column = female_column_dict.get(
        age
    )

    if female_column is not None:

        female_population_age = clean_number(
            selected_row[female_column]
        )

    else:

        female_population_age = 0


    age_data.append(
        {
            "연령": age,
            "연령표시": age_label,
            "전체": total_population_age,
            "남성": male_population_age,
            "여성": female_population_age
        }
    )


age_df = pd.DataFrame(
    age_data
)


# =========================================================
# 20. 총인구 계산
# =========================================================
total_population = int(
    age_df["전체"].sum()
)

male_population = int(
    age_df["남성"].sum()
)

female_population = int(
    age_df["여성"].sum()
)


# =========================================================
# 21. 지역 인구 현황
# =========================================================
st.divider()

st.subheader(
    f"{selected_region} 인구 현황"
)


metric1, metric2, metric3, metric4 = st.columns(
    4
)


with metric1:

    st.metric(
        label="총인구",
        value=f"{total_population:,}명"
    )


with metric2:

    st.metric(
        label="남성",
        value=f"{male_population:,}명"
    )


with metric3:

    st.metric(
        label="여성",
        value=f"{female_population:,}명"
    )


with metric4:

    if female_population > 0:

        sex_ratio = (
            male_population
            / female_population
            * 100
        )

        st.metric(
            label="성비",
            value=f"{sex_ratio:.1f}"
        )

        st.caption(
            "여성 100명당 남성 수"
        )

    else:

        st.metric(
            label="성비",
            value="-"
        )


# =========================================================
# 22. 연령별 인구구조
# =========================================================
st.divider()

st.subheader(
    "연령별 인구 구조"
)


# =========================================================
# 23. 그래프 옵션
# =========================================================
option_col1, option_col2 = st.columns(
    [2, 3]
)


with option_col1:

    age_range = st.slider(
        "표시할 연령 범위",
        min_value=0,
        max_value=100,
        value=(0, 100),
        step=1
    )


with option_col2:

    st.write(
        "그래프에 표시할 인구"
    )

    check1, check2, check3 = st.columns(
        3
    )


    with check1:

        show_total = st.checkbox(
            "전체",
            value=True
        )


    with check2:

        show_male = st.checkbox(
            "남성",
            value=True
        )


    with check3:

        show_female = st.checkbox(
            "여성",
            value=True
        )


# =========================================================
# 24. 선택 연령 범위 필터링
# =========================================================
graph_df = age_df[
    (
        age_df["연령"]
        >= age_range[0]
    )
    &
    (
        age_df["연령"]
        <= age_range[1]
    )
].copy()


# =========================================================
# 25. Plotly 그래프 생성
# =========================================================
fig = go.Figure()


# =========================================================
# 26. 전체 인구
# =========================================================
if show_total:

    fig.add_trace(

        go.Scatter(

            x=graph_df["연령"],

            y=graph_df["전체"],

            mode="lines",

            name="전체",

            line=dict(
                width=4
            ),

            hovertemplate=(
                "<b>%{x}세</b><br>"
                "전체: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# =========================================================
# 27. 남성 인구
# =========================================================
if show_male:

    fig.add_trace(

        go.Scatter(

            x=graph_df["연령"],

            y=graph_df["남성"],

            mode="lines",

            name="남성",

            line=dict(
                width=2
            ),

            hovertemplate=(
                "<b>%{x}세</b><br>"
                "남성: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# =========================================================
# 28. 여성 인구
# =========================================================
if show_female:

    fig.add_trace(

        go.Scatter(

            x=graph_df["연령"],

            y=graph_df["여성"],

            mode="lines",

            name="여성",

            line=dict(
                width=2
            ),

            hovertemplate=(
                "<b>%{x}세</b><br>"
                "여성: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# =========================================================
# 29. Plotly 디자인
# =========================================================
fig.update_layout(

    title=dict(
        text=(
            f"{selected_region} 연령별 인구 구조"
        ),

        x=0.5,

        xanchor="center"
    ),

    xaxis_title="연령",

    yaxis_title="인구수(명)",

    hovermode="x unified",

    template="plotly_white",

    height=650,

    margin=dict(
        l=40,
        r=30,
        t=80,
        b=50
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5
    )
)


# =========================================================
# 30. X축 설정
# =========================================================
fig.update_xaxes(

    tickmode="linear",

    tick0=0,

    dtick=5,

    range=[
        age_range[0],
        age_range[1]
    ],

    showgrid=True
)


# =========================================================
# 31. Y축 설정
# =========================================================
fig.update_yaxes(

    tickformat=",",

    rangemode="tozero",

    showgrid=True
)


# =========================================================
# 32. 그래프 출력
# =========================================================
st.plotly_chart(
    fig,
    use_container_width=True
)


st.caption(
    "※ 그래프의 100세는 원자료의 '100세 이상' 인구를 의미합니다."
)


# =========================================================
# 33. 가장 인구가 많은 연령
# =========================================================
if not age_df.empty:

    max_age_index = (
        age_df["전체"].idxmax()
    )

    max_age_row = age_df.loc[
        max_age_index
    ]


    st.info(
        f"""
        **{selected_region}에서 인구가 가장 많은 연령은
        {max_age_row["연령표시"]}이며,
        {int(max_age_row["전체"]):,}명입니다.**
        """
    )


# =========================================================
# 34. 주요 연령집단 계산
# =========================================================

# 유소년 인구: 0~14세
child_population = int(

    age_df.loc[
        age_df["연령"].between(
            0,
            14
        ),
        "전체"
    ].sum()
)


# 생산연령 인구: 15~64세
working_population = int(

    age_df.loc[
        age_df["연령"].between(
            15,
            64
        ),
        "전체"
    ].sum()
)


# 고령 인구: 65세 이상
elderly_population = int(

    age_df.loc[
        age_df["연령"] >= 65,
        "전체"
    ].sum()
)


# =========================================================
# 35. 주요 연령집단 비율
# =========================================================
if total_population > 0:

    child_ratio = (
        child_population
        / total_population
        * 100
    )

    working_ratio = (
        working_population
        / total_population
        * 100
    )

    elderly_ratio = (
        elderly_population
        / total_population
        * 100
    )

else:

    child_ratio = 0
    working_ratio = 0
    elderly_ratio = 0


# =========================================================
# 36. 주요 연령집단 출력
# =========================================================
st.divider()

st.subheader(
    "주요 연령집단"
)


group1, group2, group3 = st.columns(
    3
)


with group1:

    st.metric(
        "유소년 인구",
        f"{child_population:,}명"
    )

    st.caption(
        f"0~14세 · 전체의 {child_ratio:.1f}%"
    )


with group2:

    st.metric(
        "생산연령 인구",
        f"{working_population:,}명"
    )

    st.caption(
        f"15~64세 · 전체의 {working_ratio:.1f}%"
    )


with group3:

    st.metric(
        "고령 인구",
        f"{elderly_population:,}명"
    )

    st.caption(
        f"65세 이상 · 전체의 {elderly_ratio:.1f}%"
    )


# =========================================================
# 37. 10세 단위 연령대 분류
# =========================================================
def make_age_group(age):

    if age <= 9:
        return "0~9세"

    elif age <= 19:
        return "10~19세"

    elif age <= 29:
        return "20~29세"

    elif age <= 39:
        return "30~39세"

    elif age <= 49:
        return "40~49세"

    elif age <= 59:
        return "50~59세"

    elif age <= 69:
        return "60~69세"

    elif age <= 79:
        return "70~79세"

    elif age <= 89:
        return "80~89세"

    else:
        return "90세 이상"


age_df["연령대"] = (
    age_df["연령"]
    .apply(
        make_age_group
    )
)


# =========================================================
# 38. 연령대별 집계
# =========================================================
age_group_df = (

    age_df
    .groupby(
        "연령대",
        sort=False
    )[
        [
            "전체",
            "남성",
            "여성"
        ]
    ]
    .sum()
    .reset_index()
)


# =========================================================
# 39. 연령대 비율 계산
# =========================================================
if total_population > 0:

    age_group_df["인구비율(%)"] = (

        age_group_df["전체"]
        / total_population
        * 100

    ).round(1)

else:

    age_group_df["인구비율(%)"] = 0


# =========================================================
# 40. 연령대별 표
# =========================================================
st.divider()

st.subheader(
    "10세 단위 연령대별 인구"
)


st.dataframe(

    age_group_df,

    column_config={

        "연령대":
            st.column_config.TextColumn(
                "연령대"
            ),

        "전체":
            st.column_config.NumberColumn(
                "전체",
                format="%d명"
            ),

        "남성":
            st.column_config.NumberColumn(
                "남성",
                format="%d명"
            ),

        "여성":
            st.column_config.NumberColumn(
                "여성",
                format="%d명"
            ),

        "인구비율(%)":
            st.column_config.NumberColumn(
                "전체 인구 중 비율",
                format="%.1f%%"
            )
    },

    hide_index=True,

    use_container_width=True
)


# =========================================================
# 41. 상세 데이터
# =========================================================
with st.expander(
    "연령별 상세 데이터 보기"
):

    detail_df = age_df[
        [
            "연령표시",
            "전체",
            "남성",
            "여성"
        ]
    ].copy()


    detail_df.columns = [
        "연령",
        "전체",
        "남성",
        "여성"
    ]


    st.dataframe(

        detail_df,

        column_config={

            "연령":
                st.column_config.TextColumn(
                    "연령"
                ),

            "전체":
                st.column_config.NumberColumn(
                    "전체",
                    format="%d명"
                ),

            "남성":
                st.column_config.NumberColumn(
                    "남성",
                    format="%d명"
                ),

            "여성":
                st.column_config.NumberColumn(
                    "여성",
                    format="%d명"
                )
        },

        hide_index=True,

        use_container_width=True
    )


# =========================================================
# 42. 데이터 파일 확인용 정보
# =========================================================
with st.expander(
    "데이터 파일 정보"
):

    st.write(
        "사용 중인 데이터 파일:"
    )

    st.code(
        TARGET_FILE_NAME
    )

    st.write(
        f"데이터 행 수: {len(df):,}"
    )

    st.write(
        f"데이터 열 수: {len(df.columns):,}"
    )

    st.write(
        f"검색 가능한 지역 수: {df['지역명'].nunique():,}"
    )


# =========================================================
# 43. 하단
# =========================================================
st.divider()


if year_month:

    st.caption(
        f"자료: 주민등록 연령별 인구현황 · {year_month}"
    )

else:

    st.caption(
        "자료: 주민등록 연령별 인구현황"
    )
