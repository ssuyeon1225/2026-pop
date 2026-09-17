import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re


# =========================================================
# 1. 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="지역별 인구구조 분석",
    page_icon="👥",
    layout="wide"
)

st.title("지역별 연령 인구구조 분석")

st.markdown(
    """
    지역명을 검색하고 원하는 지역을 선택하면,
    해당 지역의 **연령별 전체·남성·여성 인구 구조**를
    한눈에 확인할 수 있습니다.
    """
)


# =========================================================
# 2. 데이터 파일 설정
# =========================================================
FILE_NAME = "202608_202608_연령별인구현황_월간.csv"


# =========================================================
# 3. CSV 불러오기
# =========================================================
@st.cache_data
def load_data():
    """
    행정안전부 주민등록 인구통계 CSV 파일을 불러옵니다.
    현재 파일은 CP949 인코딩을 기준으로 읽습니다.
    """

    df = pd.read_csv(
        FILE_NAME,
        encoding="cp949",
        low_memory=False
    )

    return df


try:
    df = load_data()

except FileNotFoundError:

    st.error(
        f"""
        데이터 파일을 찾을 수 없습니다.

        app.py와 같은 폴더에 아래 파일이 있는지 확인하세요.

        {FILE_NAME}
        """
    )

    st.stop()

except Exception as e:

    st.error(
        f"데이터를 불러오는 중 오류가 발생했습니다.\n\n{e}"
    )

    st.stop()


# =========================================================
# 4. 숫자 문자열 정리 함수
# =========================================================
def clean_number(value):
    """
    예:
    '9,281,625' -> 9281625
    """

    if pd.isna(value):
        return 0

    value = str(value).replace(",", "").strip()

    try:
        return int(float(value))

    except (ValueError, TypeError):
        return 0


# =========================================================
# 5. 연령별 열 찾는 함수
# =========================================================
def find_age_columns(dataframe, gender):
    """
    gender:
        계 = 전체
        남 = 남성
        여 = 여성

    예:
        2026년08월_계_0세
        2026년08월_남_35세
        2026년08월_여_100세 이상
    """

    result = []

    pattern = re.compile(
        rf"^\d{{4}}년\d{{2}}월_{gender}_(\d+세|100세 이상)$"
    )

    for column in dataframe.columns:

        match = pattern.match(str(column))

        if match is None:
            continue

        age_label = match.group(1)

        if age_label == "100세 이상":
            age = 100

        else:
            age = int(
                age_label.replace("세", "")
            )

        result.append(
            {
                "age": age,
                "label": age_label,
                "column": column
            }
        )

    result.sort(
        key=lambda x: x["age"]
    )

    return result


# =========================================================
# 6. 데이터 구조 확인
# =========================================================
if "행정구역" not in df.columns:

    st.error(
        "'행정구역' 열을 찾을 수 없습니다."
    )

    st.stop()


# =========================================================
# 7. 지역명 정리
# =========================================================
# 원본 예시:
# 서울특별시 종로구 (1111000000)
#
# 화면 표시:
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
# 8. 기준年月 자동 확인
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

        year_month = f"{year}년 {month}월"

        break


if year_month:

    st.caption(
        f"주민등록 인구통계 기준: {year_month}"
    )


# =========================================================
# 9. 연령별 열 목록 만들기
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
        "전체 연령별 인구 열을 찾을 수 없습니다."
    )

    st.stop()


# =========================================================
# 10. 지역 선택 영역
# =========================================================
st.divider()

st.subheader("지역 선택")


# -------------------------
# 지역명 입력
# -------------------------
search_keyword = st.text_input(
    "지역명을 입력하세요",
    placeholder="예: 서울, 종로구, 강남구, 수원시"
)


# -------------------------
# 입력한 검색어로 필터링
# -------------------------
if search_keyword.strip():

    filtered_df = df[
        df["지역명"]
        .str.contains(
            search_keyword.strip(),
            case=False,
            na=False
        )
    ]

else:

    filtered_df = df


# -------------------------
# 선택 가능한 지역 목록
# -------------------------
region_options = (
    filtered_df["지역명"]
    .dropna()
    .drop_duplicates()
    .tolist()
)


if len(region_options) == 0:

    st.warning(
        f"'{search_keyword}'에 해당하는 지역이 없습니다."
    )

    st.stop()


selected_region = st.selectbox(
    "검색 결과에서 지역을 선택하세요",
    options=region_options
)


# =========================================================
# 11. 선택 지역 행 추출
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
# 12. 연령별 DataFrame 만들기
# =========================================================
age_data = []


# 각 연령을 기준으로 열 매칭
male_column_dict = {
    item["age"]: item["column"]
    for item in male_age_columns
}

female_column_dict = {
    item["age"]: item["column"]
    for item in female_age_columns
}


for item in total_age_columns:

    age = item["age"]
    age_label = item["label"]
    total_column = item["column"]


    total_population = clean_number(
        selected_row[total_column]
    )


    male_column = male_column_dict.get(age)

    if male_column is not None:

        male_population = clean_number(
            selected_row[male_column]
        )

    else:

        male_population = 0


    female_column = female_column_dict.get(age)

    if female_column is not None:

        female_population = clean_number(
            selected_row[female_column]
        )

    else:

        female_population = 0


    age_data.append(
        {
            "연령": age,
            "연령표시": age_label,
            "전체": total_population,
            "남성": male_population,
            "여성": female_population
        }
    )


age_df = pd.DataFrame(age_data)


# =========================================================
# 13. 총인구 계산
# =========================================================
total_population = age_df["전체"].sum()

male_population = age_df["남성"].sum()

female_population = age_df["여성"].sum()


# =========================================================
# 14. 주요 인구 지표
# =========================================================
st.divider()

st.subheader(
    f"{selected_region} 인구 현황"
)


metric1, metric2, metric3, metric4 = st.columns(4)


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
# 15. 연령별 인구구조
# =========================================================
st.divider()

st.subheader(
    "연령별 인구 구조"
)


# =========================================================
# 16. 그래프 설정
# =========================================================
setting_col1, setting_col2 = st.columns(
    [2, 3]
)


with setting_col1:

    age_range = st.slider(
        "표시할 연령 범위",
        min_value=0,
        max_value=100,
        value=(0, 100),
        step=1
    )


with setting_col2:

    st.write("표시할 인구 유형")

    checkbox1, checkbox2, checkbox3 = st.columns(3)

    with checkbox1:

        show_total = st.checkbox(
            "전체",
            value=True
        )

    with checkbox2:

        show_male = st.checkbox(
            "남성",
            value=True
        )

    with checkbox3:

        show_female = st.checkbox(
            "여성",
            value=True
        )


# =========================================================
# 17. 그래프용 데이터 필터링
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
# 18. Plotly 꺾은선 그래프
# =========================================================
fig = go.Figure()


# -------------------------
# 전체
# -------------------------
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
                "전체 인구: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# -------------------------
# 남성
# -------------------------
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
                "남성 인구: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# -------------------------
# 여성
# -------------------------
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
                "여성 인구: %{y:,}명"
                "<extra></extra>"
            )
        )
    )


# =========================================================
# 19. 그래프 디자인
# =========================================================
fig.update_layout(

    title=dict(
        text=f"{selected_region} 연령별 인구 구조",
        x=0.5,
        xanchor="center"
    ),

    xaxis_title="연령",

    yaxis_title="인구수(명)",

    hovermode="x unified",

    template="plotly_white",

    height=650,

    margin=dict(
        l=30,
        r=30,
        t=80,
        b=40
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
# 20. X축 설정
# =========================================================
fig.update_xaxes(

    tickmode="linear",

    tick0=0,

    dtick=5,

    range=[
        age_range[0],
        age_range[1]
    ],

    showgrid=True,

    title_font=dict(
        size=15
    )
)


# =========================================================
# 21. Y축 설정
# =========================================================
fig.update_yaxes(

    tickformat=",",

    rangemode="tozero",

    showgrid=True,

    title_font=dict(
        size=15
    )
)


# =========================================================
# 22. Plotly 그래프 출력
# =========================================================
st.plotly_chart(
    fig,
    use_container_width=True
)


st.caption(
    "※ 그래프에서 100세는 원자료의 '100세 이상'을 의미합니다."
)


# =========================================================
# 23. 인구가 가장 많은 연령 찾기
# =========================================================
if not age_df.empty:

    max_age_row = age_df.loc[
        age_df["전체"].idxmax()
    ]

    st.info(
        f"""
        **{selected_region}에서 인구가 가장 많은 연령은
        {max_age_row['연령표시']}이며,
        {max_age_row['전체']:,}명입니다.**
        """
    )


# =========================================================
# 24. 주요 연령집단 계산
# =========================================================
child_population = age_df.loc[
    age_df["연령"].between(
        0,
        14
    ),
    "전체"
].sum()


working_population = age_df.loc[
    age_df["연령"].between(
        15,
        64
    ),
    "전체"
].sum()


elderly_population = age_df.loc[
    age_df["연령"] >= 65,
    "전체"
].sum()


# =========================================================
# 25. 연령집단 비율
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
# 26. 연령집단 요약
# =========================================================
st.divider()

st.subheader(
    "주요 연령집단"
)


group_col1, group_col2, group_col3 = st.columns(3)


with group_col1:

    st.metric(
        "유소년 인구",
        f"{child_population:,}명"
    )

    st.caption(
        f"0~14세 · {child_ratio:.1f}%"
    )


with group_col2:

    st.metric(
        "생산연령 인구",
        f"{working_population:,}명"
    )

    st.caption(
        f"15~64세 · {working_ratio:.1f}%"
    )


with group_col3:

    st.metric(
        "고령 인구",
        f"{elderly_population:,}명"
    )

    st.caption(
        f"65세 이상 · {elderly_ratio:.1f}%"
    )


# =========================================================
# 27. 10세 단위 연령대 함수
# =========================================================
def age_group(age):

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


# =========================================================
# 28. 연령대별 요약 데이터
# =========================================================
age_df["연령대"] = age_df["연령"].apply(
    age_group
)


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


if total_population > 0:

    age_group_df["인구비율(%)"] = (
        age_group_df["전체"]
        / total_population
        * 100
    ).round(1)

else:

    age_group_df["인구비율(%)"] = 0


# =========================================================
# 29. 연령대별 표
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
# 30. 연령별 상세 데이터
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
# 31. 하단 정보
# =========================================================
st.divider()

st.caption(
    f"자료: 주민등록 연령별 인구현황 · {year_month if year_month else '기준월 미확인'}"
)
