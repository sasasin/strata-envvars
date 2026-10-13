# `STRATA_PREFILL_EQUAL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有の CUDA/HIP 共通実装と SYCL 実装。外部ライブラリの環境変数動作は対象外。

## 役割

prompt prefill の区間について、expert cache から一時的に借りる prefill buffer の chunk 容量を、通常の「最大 chunk と短い末尾」になりにくい大きさへ調整します。単一 prompt の cache loan と、serve の各参加 stage に対する loan の sizing に使われます。値の判定だけで実際の chunk 形状が必ず変わるわけではなく、区間長や末尾 chunk の条件によって通常の sizing に戻ります。

## 値と判定

CUDA/HIP 共通コードと SYCL コードの両方で、環境変数の先頭文字が `'1'` かを判定します。数値変換や文字列全体の比較はしません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| それ以外（例: `0`, `true`, ` 1`） | 無効 |

大文字小文字や後続文字の検査はありません。読み取り結果は関数内の `static const bool` に保存され、最初に sizing 関数の実行経路へ到達した後は同一プロセスで再評価されません。サーバーの後続リクエスト中に環境を書き換えても反映されません。

## 有効になる条件

有効判定に加えて、次の条件を満たす sizing 箇所でのみ結果が使われます。

- prompt の token 数と最大 chunk が正で、通常計算の `n = ceil(tokens / max_chunk)` が 2 以上。
- 通常の分割でできる末尾 chunk `tokens - (n - 1) * max_chunk` が `Prefill::stream_all_min_tokens()` 以上。
- 対象 prompt 経路が cache loan を使う。単一 prompt では `--prefill` 相当の chunk が正で、`--no-prefill-borrow` ではなく、resident expert/cache の借用元があること。serve では stage の prefill parts が存在すること。

条件を満たさない場合は従来の `request_chunk()` の値を使います。serve の短い request で `STRATA_SPLIT_SMALL_OWN` が適用される場合は、さらにその値で上限を絞ります。`request_chunk()` 自体は変更しないため、同じ関数内でも `STRATA_SPLIT_SMALL_OWN` 等の別用途にはこの設定が適用されません。

`stream_all_min_tokens()` は別設定の影響を受けます。CUDA/HIP 共通 prefill では既定 1024 tokens で、`STRATA_PREFILL_STREAM_MIN` または CPU share の状態により変わります。SYCL prefill では既定 1024 tokens、`STRATA_PREFILL_STREAM_MIN` が設定されていればその `atoll()` 値です。この閾値未満の通常末尾 chunk は equal sizing の対象外です。

## 実行時の詳細

通常 chunk は、正の token 数を 256 単位に切り上げ、`max_chunk` で上限を設けます。equal sizing が有効で条件も満たす場合、通常分割数 `n` は維持し、`ceil(tokens / n)` を 256 単位に切り上げた値を chunk 容量として返します（`max_chunk` を超えないよう再度 clamp）。従って、実際の chunk 容量や buffer 形状の切り上げが変わります。コードはこの値を、serve では各 request segment の loan と buffer relayout に、単一 prompt では prompt 部分の必要量と loan slot 数の決定に使います。単一 prompt が cache loan を使わない場合、この変数によるサイズ変更はありません。

設定値自体について、Strata はログ、警告、エラーを出しません。後続の既存 buffer allocation/relayout が失敗した場合は通常の prefill エラー経路になります。調査対象ソースに、この環境変数固有の値表示や fallback ログはありません。

`docs/DETAILS.md` はこの設定を「prompt segment を等しい chunk サイズで読み、短い末尾をなくす（丸めが変わる）」 opt-in と記載しています。実装では 256-token 単位の丸めと `stream_all_min_tokens()` による条件があるため、全ての区間で無条件に chunk サイズが変わるわけではありません。資料中にこの変数の性能測定値はありません。

## 根拠

- `src/program/generate.cpp:6326-6349`: 通常/equal chunk の計算と環境値の読み取り。
- `src/program/generate.cpp:10895-10906,12567-12586`: serve request loan と単一 prompt の sizing への適用。
- `sycl/src/program/generate.cpp:5973-5997,10141-10152,11689-11708`: SYCL 側の同じ判定および適用箇所。
- `src/prefill/prefill.cpp:143-153,1823`: CUDA/HIP 共通側の streaming threshold と accessor。`STRATA_PREFILL_STREAM_MIN` と CPU share による条件差。
- `sycl/src/prefill/prefill.cpp:115-121,1849`: SYCL 側の streaming threshold と accessor。
- `src/prefill/prefill.cpp:1312-1338`、`sycl/src/prefill/prefill.cpp:1250-1277`: loan buffer の relayout が指定 chunk 容量で領域を作り直す。
- `docs/DETAILS.md:260-271`: 機能の説明。ソースの判定条件を優先して記載。
