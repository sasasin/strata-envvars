# `STRATA_ESIMD_DBG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL の Battlemage 向け int8 DPAS (ESIMD) prompt attention kernel に渡す整数ビットフラグです。mask `0x2` は Q.K 計算をスキップし、mask `0x10` は K/V 読み込みの fast path を無効にします。通常の利用者向け設定というより、kernel の診断・経路確認用です。設定値によるログ出力はありません。

## 値と判定

`qsa_prompt_attn_esimd()` の呼び出しごとに `getenv("STRATA_ESIMD_DBG")` を調べ、未設定なら `0`、設定されていれば `atoi()` の結果を `Args::dbg` に渡します。値全体の検証や範囲制限はありません。

| 環境値 | `dbg` の扱い |
|---|---|
| 未設定 | `0` |
| 空文字 | `atoi("")` により `0` |
| 変換可能な数字部分がない文字列 | `atoi()` により `0` |
| 符号・先頭空白を含む整数 | `atoi()` が変換した整数を使用 |
| 整数の後ろに文字が続く値 | 数字部分の整数を使用（例: `16xyz` は `16`） |
| 整数範囲外 | コードに検査・clamp はない。`atoi()` の結果は保証されない |

利用される mask は `0x2` と `0x10` です。たとえば `18` は両方を指定します。他のビットはこのファイルでは参照されません。CLI 引数、設定ファイル、別環境変数による上書きはありません。

## 有効になる条件

この値が効果を持つのは、SYCL の `qsa_prompt_attn_esimd()` 実装がビルドされ、prompt attention の呼び出しがそこへ到達した場合です。実装は、int8 の K/V pool、対応する head geometry、正の page size などを確認し、現在の GPU 世代が Battlemage である場合に kernel を起動します。どれかの条件を満たさないと `false` を返し、呼び出し元は XMX prompt attention を試し、それも使えなければ旧 kernel に fallback します。

`STRATA_PROMPT_ATTN_ESIMD` はこの経路自体を制御します。未設定時は `1`、設定時は `atoi()` の結果を使い、結果が `0` なら ESIMD 経路を使いません。これは関数内の `static const` に一度だけ保存されます。一方、`STRATA_ESIMD_DBG` は関数呼び出しごとに読み、prompt query の chunk に複製した `Args` を通じて kernel に渡します。ビルド時に `STRATA_I8_NO_ESIMD` が定義される場合、この関数は常に `false` を返す stub となり、環境値は読まれません。

## 実行時の詳細

- `dbg & 16` が真なら、Q.K と P.V の両方で連続行用の fast load 判定を無効化し、通常の block load 経路を選びます。値が偽なら、行が連続しているとき fast load を使えます。
- `dbg & 2` が真なら、各 super-step の Q.K tile ループで `qk_tile()` の呼び出しを `continue` で飛ばします。その後の処理は score 領域を読み、softmax と P.V 計算を続けるため、通常の attention 結果を得る設定ではありません。
- それ以外のビットはこの kernel で分岐に使われません。

環境値を読んだ後に出す専用ログや警告、専用終了処理はありません。kernel が選択されたときは、初回だけ stderr に `strata: prompt attention on the int8 DPAS (ESIMD)` と出します。このログは `STRATA_ESIMD_DBG` の有無や値を示しません。

## 根拠

- `sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:90-103,338-343,379-383,405-437` — `Args::dbg`、bit 判定、値の取得、ESIMD kernel の前提条件・起動・ログ。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:2011-2015` — ESIMD、XMX、旧 kernel への dispatch 順。
- `sycl/CMakeLists.txt:50-63`、`sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:37,440-443` — ESIMD を無効にした build での stub と fallback。
- `docs/DETAILS.md` — `STRATA_ESIMD_DBG` の説明は見つからず。上記の挙動は調査対象 commit の実装に基づく。
