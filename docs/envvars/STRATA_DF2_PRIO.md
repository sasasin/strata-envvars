# `STRATA_DF2_PRIO`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

DFlash2 drafter が作る2本の GPU stream の優先度を選びます。通常の CUDA build では既定で高優先度、HIP build では既定で通常優先度です。コード上の狙いは、verifier の非同期 commit と重なる draft round が GPU 上で待ち行列の後ろに回るのを避けることです。変数が変えるのは DFlash2 の2 stream の作成時の優先度であり、engine の他の stream の優先度を直接変更しません。

この機能は CUDA/HIP build にある DFlash2 実装で使われます。Metal/SYCL build には DFlash2 が含まれません。通常の `strata generate` では `--draft dflash2` を選び、必要な MTP fallback 等の条件を満たした場合に drafter がロードされます。

## 値と判定

値全体を parse せず、最初の1文字だけを比較します。空文字は unset とは異なり、設定済みの空文字列として判定されます。

| build | unset | 設定値で高優先度になる条件 | それ以外 |
|---|---|---|---|
| CUDA | 高優先度（既定） | 先頭文字が `0` ではない。空文字、`false`、`2` も高優先度 | 先頭文字が `0`（例: `0`, `0anything`）なら通常優先度 |
| HIP | 通常優先度（既定） | 先頭文字が `1`（例: `1`, `10`, `1anything`） | unset、空文字、`true`, `2`, `0` などは通常優先度 |

大文字小文字、空白、後続文字は検査しません。たとえば CUDA では `false` も高優先度ですが、HIP では高優先度になりません。

判定結果は `load()` 内の `static const bool` に保存されます。プロセス内で最初に該当する `load()` が判定した後、環境変数を変更しても再評価されず、後から作る drafter instance にも同じ結果が使われます。

根拠: `src/core/dflash2.cpp:195-207`。

## 有効になる条件

- DFlash2 が build に含まれ、`Dflash2Drafter::load()` が stream 作成まで進む必要があります。CMake は DFlash2 を CUDA/HIP build に加え、Metal/SYCL build では含めません（`CMakeLists.txt:335-340`）。
- 通常の `strata generate` 経路では `--draft dflash2` を指定し、`--mtp` と `--spec 2` 以上、native pack、単一 GPU の CLI 実行、`--draft-model PACK` などの条件が必要です。条件を満たさない場合は DFlash2 をロードせず MTP が使われます（`src/program/generate.cpp:5474-5479`）。
- HIP では高優先度の選択と、2本目の stream を実際に使うことは別です。2本目は `STRATA_DF2_FORK` が有効で、profile が無効のときに capture 中の context 計算を分岐させる用途です。HIP で `STRATA_DF2_PRIO=1` だけを設定しても、通常設定の `STRATA_DF2_FORK` が fork を無効にしているため、通常は1本目だけが計算に使われます（`src/core/dflash2.cpp:440-460`）。CUDA では fork の既定値が有効です。

## 実行時の詳細

`load()` は CUDA/HIP 優先度範囲を取得し、高優先度なら返された最高優先度 `prio_hi`、無効なら `0` を使って `cs_` と `cs2_` を non-blocking stream として作ります。HIP では高優先度を選んだときだけ優先度範囲を取得します。優先度範囲取得 API の戻り値はこの箇所で検査されません。stream の作成に失敗すると `load()` は `dflash2: stream` を返します。`generate` はこの失敗を表示し、MTP drafter に fallback します（`src/core/dflash2.cpp:197-210`, `src/program/generate.cpp:5510-5516`）。

成功時にこの変数や選択された優先度を示す専用ログはありません。通常の DFlash2 有効ログは drafter の読み込み、binding、capture 後に出ます（`src/program/generate.cpp:16153-16165`）。優先度指定が実際の実行順や速度をどの程度変えるかは、Strata のコードと `docs/DETAILS.md` の記載からは定量化できません。

## 根拠

- `src/core/dflash2.cpp:195-207`: CUDA/HIP ごとの既定値、先頭文字判定、優先度を指定した2 stream の作成。
- `src/core/dflash2.cpp:440-460`: fork stream の既定値と `STRATA_DF2_FORK` による2本目の stream の利用条件。
- `src/program/generate.cpp:5474-5482,5510-5516`: CLI 経路でのロード条件とロード失敗時の MTP fallback。
- `CMakeLists.txt:335-340`: DFlash2 が CUDA/HIP build に含まれること。

