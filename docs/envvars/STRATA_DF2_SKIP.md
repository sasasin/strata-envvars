# `STRATA_DF2_SKIP`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

DFlash2 drafter の context 更新や block 推論の一部を省きます。ソースコメントは計測用途としています。対象名をカンマ区切りで渡す例は `attn,head,ctx,mlp,qkvo` ですが、実装はカンマ区切りの解析をせず、環境変数全体から処理ラベルを部分文字列検索します。

## 値と判定

`skip_part(what)` は、最初に呼ばれた時点で `getenv("STRATA_DF2_SKIP")` の値を `static const std::string` に保存し、空でなく、保存した文字列に `what` が含まれていれば `true` を返します。

| 環境変数 | 判定 |
|---|---|
| 未設定 | 空文字列として扱い、何も省かない |
| 明示的な空文字列 | 未設定と同じ |
| `attn` | `attn` の処理を省く |
| `attn,head` | `attn` と `head` の処理を省く |
| `small` | `small` とラベルが完全に一致する省略対象処理を省く |
| `ATTN` | 大文字小文字を区別するため `attn` には一致しない |
| 任意の文字列 | その文字列に処理ラベルが部分文字列として含まれる場合だけ該当処理を省く。数値変換や値の妥当性検査はない |

たとえば `xattny` も `attn` に一致します。`,` は区切り文字として特別扱いされません。評価結果は最初の呼び出しでキャッシュされるため、その後プロセス内で環境を書き換えても反映されません。初回呼び出しが DFlash2 の context 記録か block 記録かによって読み取り時点が決まり、要求ごとには読み直しません。

## 有効になる条件

- DFlash2 drafter を含む CUDA または HIP ビルドである必要があります。CMake は `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` のとき DFlash2 を含め、Metal と SYCL のビルドには含めません。
- 実行時に `--draft dflash2` を選び、必要な `--mtp`、native pack、`--spec 2` 以上、`--draft-model PACK` などの条件を満たす必要があります。この経路は単一 GPU の CLI 実行向けで、`--serve`、`--batch`、複数 GPU / layer split では選択されません。
- verifier が taps を保持できず DFlash2 を使えない場合、または bind / graph prepare に失敗した場合は MTP drafter に切り替わります。その場合 `skip_part()` の呼び出しは実行されません。
- 判定は profiling 専用モードに限定されていません。環境変数が設定され、DFlash2 が使われる経路では、通常の DFlash2 実行でも同じ省略が適用されます。

## 実行時の詳細

`ctx` は `record_context()` の冒頭で一致すると関数を成功扱いで返し、DFlash2 の context 表現と K/V ring 更新を省きます。block 側では、`tiny` が attention / MLP の動的畳み込み用 projection、`small` が畳み込み・正規化・量子化など、`qkvo` が Q/K/V/O projection、`attn` が attention、`mlp` が gate/up/down projection、`head` が draft head の行列積を省きます。各スキップ対象の後に置かれた profiler の `stamp()` は呼ばれますが、該当する計算処理は実行されません。

これらの処理は、後続段の入力や最終的な draft token / 確率の計算に使われます。したがって省略は drafter の候補を通常と異なるものにし得ます。生成ループは DFlash2 の draft を verifier に渡してから次の round の候補を作りますが、この環境変数自体が通常のモデル出力を保つ保証はありません。計測用として使い、通常の推論品質や処理時間を表す設定として解釈しないでください。

値の読み取りや処理省略について、この変数固有のログはありません。ソースコメントは計測用としていますが、`docs/DETAILS.md` に本変数の具体的な説明や測定値は見つかりませんでした。

## 根拠

- `src/core/dflash2.cpp:77-80` — 値の読み取り、static cache、部分文字列判定。`src/core/dflash2.cpp:346-349` — `ctx` のスキップ。
- `src/core/dflash2.cpp:392-424` — `tiny`、`small`、`qkvo`、`attn`、`mlp`、`head` の各スキップ箇所と処理。
- `CMakeLists.txt:335-340` — DFlash2 が CUDA / HIP ビルドに含まれる条件。
- `src/program/generate.cpp:5474-5482,16148-16165` — DFlash2 の選択条件と MTP への切替。
- `src/program/generate.cpp:16494-16503` — DFlash2 の draft が生成ループに渡される箇所。
- `include/strata/core/dflash2.hpp:3-16,54-59` — Drafter の処理概要と context / draft API。
