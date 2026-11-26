# `STRATA_NAN_GUARD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Verifier の出力 logits 行に NaN または無限大があるかを調べ、非有限行の情報を記録する検査の ON/OFF を制御する。Strata の読み取り箇所は `Verifier::nan_guard_on()` だけで、未設定なら ON、`atoi` の結果が 0 なら OFF。OFF の場合、CUDA/HIP の verifier graph には検査 kernel が記録されず、Metal の行走査も行われない。生成 token の選択方法を変更する設定ではない。検出結果を受けて窓の token を出さず request/slot を終了する処理は `--serve` の生成経路にある。(`engine/src/core/verify.cpp:5792-5799`, `engine/src/core/verify.cpp:3138-3141`, `engine/src/core/verify.cpp:3810-3815`, `engine/src/program/generate.cpp:14547-14560`, `engine/src/program/generate.cpp:17309-17321`)

## 値と判定

`std::getenv` で値を取り、未設定なら `true`、設定済みなら `std::atoi(v) != 0` を返す。文字列全体の検証はせず、`atoi` が読む先頭の整数部分で判定する。したがって空文字、空白だけ、`true`、`false`、`0anything` は OFF。`1`、`-1`、`2tail` は ON（先頭の整数が非ゼロ）。先頭の空白や符号は `atoi` の整数変換に従う。数値として変換できない文字列は 0 相当となり OFF。明示的な範囲検査や clamp はない。CLI 引数、設定ファイル、他の環境変数による上書きはこの読み取り関数にはない。(`engine/src/core/verify.cpp:5793-5798`)

| 条件 | unset | 有効になる値（検査 ON） | 無効になる値（検査 OFF） |
|---|---|---|---|
| 共通 (`atoi` 判定) | ON | `1`, `-1`, `2tail` など変換値が非ゼロ | 空文字, `0`, `0anything`, `true`, 空白だけなど変換値が 0 |

## 有効になる条件

- `Verifier` を使う検証窓が実行されること。設定の読み取り結果は `nan_guard_on()` を通じて CUDA/HIP の検査 kernel 記録や Metal の走査に使われる。CUDA/HIP 側では head を持つ最終 stage の非 null フラグ領域が必要で、head のない stage は調べない。Metal は head を持つ最終 stage でホスト走査する。(`engine/src/core/verify.cpp:3105-3106`, `engine/src/core/verify.cpp:3138-3141`, `engine/src/core/verify.cpp:3810-3815`, `engine/src/core/verify.cpp:5825-5837`)
- 複数 GPU の layer split では、非有限行の公開 API は head を持つ最終 stage に結果を問い合わせる。(`engine/include/strata/core/verify.hpp:130-143`)
- serve の通常 request は `nonfinite_row()`、batch slot は `nonfinite_in()` を調べ、検出時にその窓の出力を止める。`STRATA_NAN_GUARD=0` では検出情報が作られないため、この非有限 logits 経由の終了・cache flush は起きない。検出経路は `--serve` の処理で確認できる。(`engine/src/program/generate.cpp:14550-14560`, `engine/src/program/generate.cpp:17309-17321`, `engine/src/program/generate.cpp:17851-17866`)
- Intel/SYCL 実装にこの名前の読み取りは見つからない。Strata の `docs/DETAILS.md` も Intel (SYCL) port を非対応としている。(`docs/DETAILS.md:661-668`; checkout 全体での名前検索ではソース上の getenv は `engine/src/core/verify.cpp:5795` のみ)

## 実行時の詳細

`nan_guard_on()` の関数ローカル `static const bool` は初回呼び出し時に一度だけ評価され、以後の verifier と窓で共有される。環境変数を初回呼び出し後に変更しても、このプロセス内の判定は変わらない。グラフが一度 capture されるため、OFF なら検査 kernel を含まない、という実装コメントとも一致する。(`engine/src/core/verify.cpp:5792-5799`)

CUDA/HIP では logits の各行を `logits_nonfinite_rows` に渡し、フラグを verifier が読み取る。Metal build にはその kernel がないため、window logits をホストから走査して同じ行 mask を作る。検査対象は NaN に限らず、指数部が全ビット 1 の float（NaN、`+inf`、`-inf`）。検出した最初の行とその位置を verifier に保存する。(`engine/src/core/verify.cpp:3105-3141`, `engine/src/core/verify.cpp:3738-3773`, `engine/src/core/verify.cpp:3810-3815`, `engine/src/core/verify.cpp:5821-5849`)

serve の通常窓で検出すると stderr に `strata serve: non-finite logits (#879) in a ... window at position ... (row ...): its tokens are not emitted, the request ends (DONE nonfinite) and the next request reads its prompt from token 0` を出す。続く request の開始時に live session、checkpoint、parked conversation、idle batch slot を破棄し、prompt を token 0 から読む。batch では stderr に `strata batch: non-finite logits (#879) ...`、stdout に `BDONE ... nonfinite ...` を出し、その slot の token を出さず cache を保持しない。環境変数の既定値や OFF 切替そのものを示すログはない。(`engine/src/program/generate.cpp:14550-14560`, `engine/src/program/generate.cpp:17309-17321`, `engine/src/program/generate.cpp:17851-17866`, `engine/src/program/generate.cpp:19242-19279`)

## ログと測定値

Strata の `docs/DETAILS.md` は、検出時の serve retry と失敗時の応答、および Metal の host scan に触れている。資料には M1 Max で約 60 µs / decode window・0.2% とある一方、現行ソースの `metal_scan_rows` コメントは M5 Max で約 1.5% と記す。対象機種と比率が異なり、比較条件もこのコードから確認できないため、現行環境一般の性能値とは扱わない。測定の再実施はしていない。(`docs/DETAILS.md:661-669`, `engine/src/core/verify.cpp:3745-3760`)

## 根拠

- `engine/src/core/verify.cpp:5792-5799` — 唯一の環境読み取り、変換、関数内 cache。
- `engine/src/core/verify.cpp:3105-3141`, `engine/src/core/verify.cpp:3738-3773`, `engine/src/core/verify.cpp:3810-3815`, `engine/src/core/verify.cpp:5821-5849` — backend ごとの検査、行・位置の記録。
- `engine/include/strata/core/verify.hpp:130-144` — 非有限情報の API と layer split の転送。
- `engine/src/program/generate.cpp:14547-14560`, `engine/src/program/generate.cpp:17309-17321`, `engine/src/program/generate.cpp:17851-17866`, `engine/src/program/generate.cpp:19242-19279` — serve の結果、出力、状態破棄。
- `docs/DETAILS.md:661-669` — 機能説明と測定記述（測定条件の照合に関する制約は上記）。
