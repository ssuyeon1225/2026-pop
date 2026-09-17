import os
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
    원하는 지역을 선택하면 해당 지역의 **연령별 인구구조**와
    전국에서 인구구조가 가장 비슷한 지역 **TOP 5**를 비교합니다.

    인구구조의 유사성은 총인구 규모가 아니라
    **0세~100세 이상 연령별 인구 비율의 분포**를 기준으로 계산합니다.
    """
)


# =========================================================
# 2. 데이터 파일명
# =========================================================
TARGET_FILE_NAME = "202608_202608_연령별인구현황_월간.csv"


# =========================================================
# 3. app.py가 있는 폴더
# =========================================================
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# =========================================================
# 4. 데이터 파일 찾기
# =========================================================
def find_data_file():

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
# 5. CSV 읽기
# =========================================================
@st.cache_data
def load_data():

    file_path = find_data_file()

    if file_path is None:

        raise FileNotFoundError(
            f"{TARGET_FILE_NAME} 파일을 찾을 수 없습니다."
        )

    encodings = [
        "cp949",
        "utf-8-sig",
        "utf-8"
    ]

    for encoding in encodings:

        try:

            return pd.read_csv(
                file_path,
                encoding=encoding,
                low_memory=False
            )

        except UnicodeDecodeError:

            continue

    raise ValueError(
        "CSV 파일의 인코딩을 확인할 수 없습니다."
    )


# =========================================================
# 6. 데이터 불러오기
# =========================================================
try:

    df = load_data()

except FileNotFoundError as e:

    st.error(str(e))

    st.write("현재 app.py 폴더에서 발견된 파일:")

    for file_name in os.listdir(BASE_DIR):
        st.write(f"- {file_name}")

    st.stop()

except Exception as e:

    st.error(
        f"데이터를 읽는 중 오류가 발생했습니다: {e}"
    )

    st.stop()


# =========================================================
# 7. 숫자 변환 함수
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

        return int(
            float(value)
        )

    except (ValueError, TypeError):

        return 0


# =========================================================
# 8. 전체 연령별 열 찾기
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
# 9. 행정구역 열 확인
# =========================================================
if "행정구역" not in df.columns:

    st.error(
        "'행정구역' 열을 찾을 수 없습니다."
    )

    st.stop()


# =========================================================
# 10. 지역명 정리
# =========================================================
# 원자료:
# 서울특별시 종로구 청운효자동(1111051500)
#
# 화면:
# 서울특별시 종로구 청운효자동

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
# 11. 행정구역 코드 추출
# =========================================================
df["행정구역코드"] = (
    df["행정구역"]
    .astype(str)
    .str.extract(
        r"\((\d+)\)"
    )[0]
)


# =========================================================
# 12. 기준 연월 찾기
# =========================================================
year_month = None

for column in df.columns:

    match = re.match(
        r"^(\d{4})년(\d{2})월_",
        str(column)
    )

    if match:

        year_month = (
            f"{match.group(1)}년 "
            f"{match.group(2)}월"
        )

        break


if year_month:

    st.caption(
        f"주민등록 인구통계 기준: {year_month}"
    )


# =========================================================
# 13. 연령별 열 찾기
# =========================================================
age_columns = find_age_columns(
    df
)


if len(age_columns) == 0:

    st.error(
        "연령별 인구 열을 찾을 수 없습니다."
    )

    st.stop()


age_column_names = [
    item["column"]
    for item in age_columns
]

age_values = [
    item["age"]
    for item in age_columns
]

age_labels = [
    item["label"]
    for item in age_columns
]


# =========================================================
# 14. 모든 지역의 연령 데이터를 숫자로 변환
# =========================================================
@st.cache_data
def prepare_population_data(
    original_df,
    columns
):

    population_df = (
        original_df[columns]
        .copy()
    )

    for column in columns:

        population_df[column] = (
            population_df[column]
            .astype(str)
            .str.replace(
                ",",
                "",
                regex=False
            )
        )

        population_df[column] = pd.to_numeric(
            population_df[column],
            errors="coerce"
        ).fillna(0)

    return population_df


population_df = prepare_population_data(
    df,
    age_column_names
)


# =========================================================
# 15. 각 지역 총인구 계산
# =========================================================
region_total_population = (
    population_df.sum(axis=1)
)


# =========================================================
# 16. 인구구조 비율 행렬 생성
# =========================================================
# 각 연령 인구 / 해당 지역 총인구
#
# 예:
# 20세 인구 2%
# 21세 인구 2.1%
# ...

population_share = population_df.div(
    region_total_population.replace(
        0,
        np.nan
    ),
    axis=0
).fillna(0)


# =========================================================
# 17. 코사인 유사도 계산용 정규화
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
# 18. 유사 지역 탐색 함수
# =========================================================
def find_similar_regions(
    selected_index,
    top_n=5
):

    # 선택 지역의 벡터
    selected_vector = (
        normalized_population_matrix[
            selected_index
        ]
    )

    # 코사인 유사도
    similarities = (
        normalized_population_matrix
        @ selected_vector
    )

    result = pd.DataFrame(
        {
            "index": df.index,
            "지역명": df["지역명"],
            "행정구역코드": df["행정구역코드"],
            "총인구": region_total_population,
            "유사도": similarities
        }
    )


    # ---------------------------------------------
    # 선택 지역 자체 제거
    # ---------------------------------------------
    result = result[
        result["index"]
        != selected_index
    ]


    # ---------------------------------------------
    # 인구가 0인 지역 제거
    # ---------------------------------------------
    result = result[
        result["총인구"] > 0
    ]


    # ---------------------------------------------
    # 유사도가 높은 순으로 정렬
    # ---------------------------------------------
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
# 19. 지역 검색 영역
# =========================================================
st.divider()

st.subheader(
    "분석할 지역 선택"
)


search_keyword = st.text_input(
    "지역명을 입력하세요",
    placeholder=(
        "예: 강남구, 종로구, "
        "청운효자동, 수원시, 서울"
    )
)


search_keyword = (
    search_keyword.strip()
)


# =========================================================
# 20. 검색 결과
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
# 21. 선택 메뉴 생성
# =========================================================
region_options = (
    filtered_df[
        [
            "지역명",
            "행정구역코드"
        ]
    ]
    .drop_duplicates()
    .copy()
)


if region_options.empty:

    st.warning(
        f"'{search_keyword}'에 해당하는 지역을 찾을 수 없습니다."
    )

    st.stop()


# =========================================================
# 22. 지역 선택용 라벨 생성
# =========================================================
region_options["선택표시"] = (
    region_options["지역명"]
    + " ("
    + region_options["행정구역코드"]
        .fillna("")
        .astype(str)
    + ")"
)


selected_display = st.selectbox(
    "지역을 선택하세요",
    region_options["선택표시"]
)


# =========================================================
# 23. 선택한 지역 찾기
# =========================================================
selected_option = region_options[
    region_options["선택표시"]
    == selected_display
].iloc[0]


selected_region = (
    selected_option["지역명"]
)

selected_code = (
    selected_option["행정구역코드"]
)


selected_rows = df[
    (
        df["지역명"]
        == selected_region
    )
    &
    (
        df["행정구역코드"]
        == selected_code
    )
]


if selected_rows.empty:

    st.error(
        "선택한 지역 데이터를 찾을 수 없습니다."
    )

    st.stop()


selected_index = (
    selected_rows.index[0]
)


# =========================================================
# 24. TOP 5 유사지역 계산
# =========================================================
similar_regions = find_similar_regions(
    selected_index,
    top_n=5
)


# =========================================================
# 25. 선택 지역 기본 정보
# =========================================================
selected_total = int(
    region_total_population.loc[
        selected_index
    ]
)


st.divider()

st.subheader(
    f"{selected_region} 분석"
)


metric1, metric2 = st.columns(2)


with metric1:

    st.metric(
        "선택 지역 총인구",
        f"{selected_total:,}명"
    )


with metric2:

    st.metric(
        "비교 지역 수",
        f"{len(df) - 1:,}개"
    )


# =========================================================
# 26. TOP 5 결과 표
# =========================================================
st.divider()

st.subheader(
    "전국 인구구조 유사 지역 TOP 5"
)


display_similarity_df = (
    similar_regions[
        [
            "지역명",
            "총인구",
            "유사도(%)"
        ]
    ]
    .copy()
)


display_similarity_df.insert(
    0,
    "순위",
    range(
        1,
        len(display_similarity_df) + 1
    )
)


st.dataframe(

    display_similarity_df,

    column_config={

        "순위":
            st.column_config.NumberColumn(
                "순위",
                format="%d"
            ),

        "지역명":
            st.column_config.TextColumn(
                "지역"
            ),

        "총인구":
            st.column_config.NumberColumn(
                "총인구",
                format="%d명"
            ),

        "유사도(%)":
            st.column_config.NumberColumn(
                "구조 유사도",
                format="%.2f%%"
            )
    },

    hide_index=True,

    use_container_width=True
)


# =========================================================
# 27. 그래프용 함수
# =========================================================
def get_region_population_share(
    region_index
):

    values = (
        population_share.loc[
            region_index
        ]
        .to_numpy(
            dtype=float
        )
        * 100
    )

    return values


# =========================================================
# 28. Plotly 비교 그래프
# =========================================================
st.divider()

st.subheader(
    "연령별 인구구조 비교"
)


st.markdown(
    """
    아래 그래프는 각 연령 인구가 해당 지역 전체 인구에서
    차지하는 **비율(%)**을 표시합니다.

    따라서 지역별 총인구 규모가 달라도
    인구구조의 모양을 직접 비교할 수 있습니다.
    """
)


# =========================================================
# 29. 표시 연령 선택
# =========================================================
age_range = st.slider(
    "표시할 연령 범위",
    min_value=0,
    max_value=100,
    value=(0, 100),
    step=1
)


# =========================================================
# 30. Plotly Figure 생성
# =========================================================
fig = go.Figure()


# =========================================================
# 31. 선택 지역 그래프
# =========================================================
selected_share = (
    get_region_population_share(
        selected_index
    )
)


age_mask = np.array(
    [
        age_range[0] <= age <= age_range[1]
        for age in age_values
    ]
)


filtered_ages = (
    np.array(age_values)[
        age_mask
    ]
)


filtered_selected_share = (
    selected_share[
        age_mask
    ]
)


fig.add_trace(

    go.Scatter(

        x=filtered_ages,

        y=filtered_selected_share,

        mode="lines",

        name=f"선택: {selected_region}",

        line=dict(
            width=5
        ),

        hovertemplate=(
            "<b>%{x}세</b><br>"
            "전체 인구 중 %{y:.2f}%"
            "<extra></extra>"
        )
    )
)


# =========================================================
# 32. 유사 지역 TOP 5 그래프 추가
# =========================================================
for rank, (_, row) in enumerate(
    similar_regions.iterrows(),
    start=1
):

    region_index = int(
        row["index"]
    )

    region_name = (
        row["지역명"]
    )

    similarity = (
        row["유사도(%)"]
    )


    region_share = (
        get_region_population_share(
            region_index
        )
    )


    filtered_region_share = (
        region_share[
            age_mask
        ]
    )


    fig.add_trace(

        go.Scatter(

            x=filtered_ages,

            y=filtered_region_share,

            mode="lines",

            name=(
                f"{rank}위 {region_name} "
                f"({similarity:.2f}%)"
            ),

            line=dict(
                width=2
            ),

            hovertemplate=(
                f"<b>{rank}위 {region_name}</b><br>"
                "%{x}세<br>"
                "전체 인구 중 %{y:.2f}%"
                "<extra></extra>"
            )
        )
    )


# =========================================================
# 33. Plotly 디자인
# =========================================================
fig.update_layout(

    title=dict(
        text=(
            f"{selected_region} vs "
            "전국 유사 인구구조 TOP 5"
        ),

        x=0.5,

        xanchor="center"
    ),

    xaxis_title="연령",

    yaxis_title="지역 전체 인구 중 비율(%)",

    template="plotly_white",

    height=750,

    hovermode="x unified",

    margin=dict(
        l=40,
        r=30,
        t=100,
        b=60
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5
    )
)


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


fig.update_yaxes(

    ticksuffix="%",

    rangemode="tozero",

    showgrid=True
)


# =========================================================
# 34. 그래프 출력
# =========================================================
st.plotly_chart(
    fig,
    use_container_width=True
)


st.caption(
    """
    ※ 100세는 원자료의 '100세 이상'을 의미합니다.
    ※ 선택 지역 자체는 유사 지역 검색에서 제외됩니다.
    """
)


# =========================================================
# 35. 유사도 막대그래프
# =========================================================
st.divider()

st.subheader(
    "TOP 5 지역의 인구구조 유사도"
)


bar_df = (
    similar_regions
    .sort_values(
        "유사도(%)",
        ascending=True
    )
)


bar_fig = go.Figure()


bar_fig.add_trace(

    go.Bar(

        x=bar_df["유사도(%)"],

        y=bar_df["지역명"],

        orientation="h",

        text=bar_df[
            "유사도(%)"
        ].map(
            lambda x: f"{x:.2f}%"
        ),

        textposition="auto",

        hovertemplate=(
            "<b>%{y}</b><br>"
            "유사도: %{x:.2f}%"
            "<extra></extra>"
        )
    )
)


bar_fig.update_layout(

    title=dict(
        text=(
            f"{selected_region}과의 "
            "인구구조 유사도"
        ),

        x=0.5
    ),

    xaxis_title="코사인 유사도 (%)",

    yaxis_title="지역",

    template="plotly_white",

    height=450,

    margin=dict(
        l=30,
        r=30,
        t=70,
        b=50
    )
)


bar_fig.update_xaxes(
    ticksuffix="%"
)


st.plotly_chart(
    bar_fig,
    use_container_width=True
)


# =========================================================
# 36. TOP 5 지역 세부정보
# =========================================================
st.divider()

st.subheader(
    "TOP 5 지역 세부정보"
)


for rank, (_, row) in enumerate(
    similar_regions.iterrows(),
    start=1
):

    region_index = int(
        row["index"]
    )

    region_name = (
        row["지역명"]
    )

    total_pop = int(
        row["총인구"]
    )

    similarity = (
        row["유사도(%)"]
    )


    with st.expander(
        f"{rank}위 · {region_name} "
        f"· 유사도 {similarity:.2f}%"
    ):

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "총인구",
                f"{total_pop:,}명"
            )

        with col2:

            st.metric(
                "인구구조 유사도",
                f"{similarity:.2f}%"
            )


# =========================================================
# 37. 방법 설명
# =========================================================
st.divider()

with st.expander(
    "인구구조 유사도는 어떻게 계산했나요?"
):

    st.markdown(
        """
        ### 계산 방법

        각 지역의 인구수를 그대로 비교하면
        서울특별시와 작은 읍·면·동처럼 인구 규모가 다른 지역은
        비교하기 어렵습니다.

        따라서 다음 순서로 계산합니다.

        **1. 각 지역의 연령별 인구 비율 계산**

        예를 들어 어떤 지역의 총인구가 10,000명이고
        30세 인구가 200명이라면:

        ```
        30세 비율 = 200 / 10,000 = 0.02
        ```

        즉 2%입니다.

        이를 0세부터 100세 이상까지 계산하여 하나의
        **연령분포 벡터**로 만듭니다.

        **2. 전국 모든 지역과 코사인 유사도 계산**

        두 지역의 연령분포 벡터가 얼마나 같은 방향을
        가지는지 계산합니다.

        코사인 유사도가 1에 가까울수록
        연령별 인구분포의 형태가 유사합니다.

        **3. 선택한 지역 자체를 제외하고 유사도가 가장 높은
        5개 지역을 제시합니다.**

        따라서 이 분석은 단순히 총인구가 비슷한 지역을 찾는 것이 아니라
        **연령별 인구구조의 형태가 가장 비슷한 지역을 찾는 분석**입니다.
        """
    )


# =========================================================
# 38. 데이터 정보
# =========================================================
with st.expander(
    "데이터 정보"
):

    st.write(
        f"데이터 행 수: {len(df):,}"
    )

    st.write(
        f"비교 가능한 지역 수: "
        f"{(region_total_population > 0).sum():,}"
    )

    st.write(
        f"연령 구간 수: {len(age_columns):,}"
    )

    st.write(
        f"사용 데이터: {TARGET_FILE_NAME}"
    )


# =========================================================
# 39. 하단
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
