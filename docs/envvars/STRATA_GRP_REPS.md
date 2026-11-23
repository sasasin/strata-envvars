# `STRATA_GRP_REPS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_GRP_REPS` は通常の推論設定ではなく、CUDA/HIP GPU 用の `gr_parity` 診断プログラムにある fused GR の二グループ QFUSE 検査について、各 token 数で反復する回数を指定する。設定しなければ各 token 数につき 200 回、設定時は変換後の値を最低 1 回として使う（`engine/src/kernels/gr_parity.cpp:604-606,623-643`）。

この検査は合成入力を使い、グループ相対／window index の出力、直接起動／graph replay の q8_1 結果とカウンターを比較する。モデル推論の生成 token や通常の推論経路を変更しない（`engine/src/kernels/gr_parity.cpp:598-603,653-673,674-714`）。`gr_parity` は CUDA/HIP 共通 GPU engine の CMake 内で作成され、`gr_parity --selftest` としてテスト登録される（`engine/cmake/strata_gpu_engine.cmake:1,6-9,1005-1008`）。

## 値と判定

コードは `std::getenv` の null 判定で未設定を識別し、設定済みなら `std::atoi` の結果を `std::max(1, ...)` で下限 1 に丸める。値全体の検証や上限 clamp はない（`engine/src/kernels/gr_parity.cpp:605-606`）。

| 条件 | unset | 有効になる値（例） | 無効・境界になる値（例） |
|---|---|---|---|
| `STRATA_GR_V3` が無効（または未設定）で二グループ検査に入る場合 | 200 回 / token 数 | `1` → 1 回、`12` → 12 回、`  +3tail` → 3 回 | 空文字、`0`、`-2`、`true`、`x2`、`0anything` は `atoi` 結果が 0 以下または数値なしとなり 1 回 |
| `STRATA_GR_V3` の `atoi` 結果が非 0 | 変数を読まず、この検査を実行しない | 該当なし | `STRATA_GRP_REPS` の値は無視される |

`atoi` は先頭の空白と符号を許し、数値部分の後ろは検査しないため、`12tail` は 12 回となる。大文字小文字や文字列全体の真偽値比較はない。変換後の値に明示的な上限はありません。`int` の範囲を超える文字列について、このコードに独自の検証や規定動作はありません（`engine/src/kernels/gr_parity.cpp:605-606`）。

CLI 引数でこの回数を上書きする処理はない。CLI は `--selftest` だけを受け付け、その他の引数は usage を stderr に出して status 2 で終了する（`engine/src/kernels/gr_parity.cpp:752-756`）。

## 有効になる条件

- CUDA または HIP の GPU engine 構成で `gr_parity` をビルドし、その実行ファイルを起動すること。Metal / SYCL の同名実装ではなく、CUDA/HIP 共通の GPU engine CMake にあるターゲットである（`engine/cmake/strata_gpu_engine.cmake:1,6-9,1005-1008`）。
- `fused_multi_lds_parity` の実行まで到達すること。同関数内で `STRATA_GR_V3` を一度 `static` に読み、`std::atoi(v) != 0` の場合には通常の fused multi 検査を続けつつ、この二グループ QFUSE 検査だけを `if (!v3)` で飛ばす（`engine/src/kernels/gr_parity.cpp:340-342,604`）。
- `main` は `STRATA_GR_V3` が未設定なら `0` を環境へ設定してから検査を開始する。従って通常の未設定状態では本変数の回数指定が評価される。`STRATA_GR_V3` が空文字または `atoi` で 0 になる値でも同様に検査へ入る（`engine/src/kernels/gr_parity.cpp:745-751,342,604-606`）。
- `STRATA_GRP_KEEP_GOING` が設定されていると、空文字を含めて値の内容に関係なく真となる。この変数は失敗後も各 T と反復を続けるかを制御し、未設定なら最初の失敗後にループを止める。`STRATA_GRP_REPS` はこの継続条件を上書きしない（`engine/src/kernels/gr_parity.cpp:607,623,643`）。

## 実行時の詳細

`STRATA_GRP_REPS` は `fused_multi_lds_parity` の二グループ検査ブロックへ入るたびに一度読み取られる。関数内 static cache ではないが、反復ループ中に再読込もしないため、同じ検査の実行中に環境を書き換えてもその回数には反映されない。`STRATA_GR_V3` は同関数内 static に一度だけ保存される（`engine/src/kernels/gr_parity.cpp:342,604-607`）。

ループ対象は `T = kFusedGrMaxT = 8` に対する `tt = 2..8`。各 `tt` で `REPS` 回を上限にし、各反復は3モードを巡回する（グループ相対の直接起動、window-indexed の直接起動、グループ相対の graph replay）。したがって全て成功する場合は合計 `7 × REPS` 回の比較反復になる。失敗時は既定で残りの反復と後続の `tt` を打ち切る。`STRATA_GRP_KEEP_GOING` が存在する場合は継続する（`engine/include/strata/kernels/fused_gr.hpp:70-71`; `engine/src/kernels/gr_parity.cpp:623-665`）。

比較では参照 quantize と出力 byte 列を照合し、カウンター残存や出力領域外への書き込みも確認する。失敗は `g2bad` と最終 `bad` に加算され、プログラム末尾の集計が非ゼロなら終了コード 1 になる（`engine/src/kernels/gr_parity.cpp:663-714,721-740,1089-1093`）。

## ログと測定値

この変数専用の「有効」ログはない。検査の最後に stdout へ `fused GR read + q8_1 (STRATA_QFUSE), a window of two groups, T 2..8, %ld runs (%d random inputs each T), group-relative and window-indexed, direct and graph: %s` の行を出し、`%d` には `REPS` を渡す（`engine/src/kernels/gr_parity.cpp:721-723`）。個々の比較失敗では stdout に差分位置、カウンター残存、範囲外書込み等の診断が出る（同 `:668-713`）。CUDA API 呼出しが失敗した場合は stderr に `<what>: <CUDA error string>` を出し、status 1 で終了する（同 `:39-44`）。この調査では build や GPU 実行をしていないため実測値はない。

Strata の `docs/DETAILS.md`、`docs/SETTINGS.md` にこの変数または同検査の説明は見つからなかった。リポジトリ内では候補一覧以外に `terminal/data/settings-register.json` に名前の登録があるが、実際の読み取りは `gr_parity.cpp` の上記箇所だけであり、設定画面や通常エンジンからの読み取りを示す根拠ではない。

## 根拠

- `engine/src/kernels/gr_parity.cpp:598-607,623-665` — 検査目的、読み取り、反復数と各モード。
- `engine/src/kernels/gr_parity.cpp:668-740,1089-1093` — 比較・失敗表示・終了コード。
- `engine/src/kernels/gr_parity.cpp:745-756` — `STRATA_GR_V3` の既定設定と CLI 引数。
- `engine/src/kernels/gr_parity.cpp:39-44,340-342,721-723` — API error 経路、V3 cache、検査結果ログ。
- `engine/include/strata/kernels/fused_gr.hpp:70-71` — 最大 token 数。
- `engine/cmake/strata_gpu_engine.cmake:1,6-9,1005-1008` — CUDA/HIP GPU engine と `gr_parity` target / test 登録。
- `terminal/data/settings-register.json:12154-12164` — 設定登録メタデータ（読み取り実装ではない）。
