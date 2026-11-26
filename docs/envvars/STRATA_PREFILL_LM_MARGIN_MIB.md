# `STRATA_PREFILL_LM_MARGIN_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

layer-major prefill の super-chunk 用 GPU メモリを見積もるとき、空けておく VRAM の margin を MiB 単位で指定する。margin は利用可能 VRAM (`cudaMemGetInfo` の free bytes) から差し引かれ、super-chunk が収まるかの判定に使われる。バッファの実サイズやモデルの計算自体は変えず、どのサイズを採用できるかを変える（`engine/src/prefill/prefill.cpp:8113-8119, 8249-8272`）。

この変数を直接読む箇所は `lm_margin_bytes()` の一箇所である。`000_envvers.md` の候補登録に加え、Strata の `std::getenv` 読み取りが確認できる（`engine/src/prefill/prefill.cpp:8113-8118`）。

## 値と判定

設定文字列を `std::atoll` で整数変換し、その値を `1 << 20` 倍する。値全体の妥当性検査や末尾の確認はない。`atoll` の通常の変換規則では先頭の空白と符号を受け付け、数字列の後ろは読み飛ばされ、数字が始まらない文字列は 0 になる。従って空文字・`abc`・`0anything` は 0 MiB、`1anything` は 1 MiB、`  +2 MiB` は 2 MiB として扱われる。大文字小文字の区別はない（文字列比較ではない）。読み取りと変換は `engine/src/prefill/prefill.cpp:8113-8118`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・注意が必要な値 |
|---|---|---|---|
| 全ビルド（layer-major の CUDA メモリ見積もり経路） | 内部 sentinel `-1` となり、後述の fallback margin を使う | 変換後が 0 以上ならその MiB 数。`0` / 空文字は margin 0、`1` は 1 MiB | 変換後が負なら fallback margin に戻る。ただし負数は左シフト演算にも渡され、C++ では負の符号付き値の左シフトは未定義動作。`atoll` による `int64_t` 範囲外の入力や、MiB へのシフトで表現範囲を超える値も安全な境界として保証されない |

未設定時の fallback は `by_default == true` なら 512 MiB、それ以外は 96 MiB。設定値が通常の非負値ならこの二つを置き換える。設定値の処理は `engine/src/prefill/prefill.cpp:8114-8118`。

## 有効になる条件

- CUDA prefill の layer-major 経路が選ばれ、super-chunk の VRAM fit 判定まで到達したときに使われる。HIP ビルドでは `STRATA_LM_HIP=1` がない限り準備時点で辞退する（`engine/src/prefill/prefill.cpp:8166-8178`）。
- layer-major 自体が有効である必要がある。`STRATA_PREFILL_LAYER_MAJOR` の明示値が設定されていればそれが選択を決める。現行 `prefill_layer_major_default()` は全条件で false を返すため、未設定時に自動で有効にはならない（`engine/src/prefill/prefill.cpp:8082-8086, 9657-9662`; `engine/include/strata/core/sm120_series.hpp:184-192`）。自動 chunk sizing の単一 GPU small-card 経路は条件を満たせば `STRATA_PREFILL_LAYER_MAJOR=1` をプロセス環境に設定する。ただし `STRATA_PF_SMALL=0`、ユーザー指定の `STRATA_PF_FUSED` / `STRATA_PREFILL_LAYER_MAJOR`、auto 以外の `--prefill` などでその経路・切替が抑止される（`engine/src/program/generate.cpp:12538-12566, 12572-12612`）。
- `lm_prepare()` は、モデル未初期化、layer-split handoff、peer GPU、特定の split での PLE、画像 prompt、KVA、chunk boundary で yield する batch、`--prefill-pipe` による固定 chunk、対応しない expert layout / buffer 不足などで fit 判定前に辞退する（`engine/src/prefill/prefill.cpp:8166-8209, 8210-8234`）。これらのとき margin 値は読まれないことがある。
- `STRATA_PREFILL_LM_R` が `vram` の場合は残差行も VRAM に置く fit を判定し、`host` の場合は pinned host 側に置く前提で判定する。未設定・その他の文字列では自動選択となる。したがって同じ margin でも配置方式により必要 VRAM が異なる（`engine/src/prefill/prefill.cpp:8102-8109, 8263-8272`）。
- `STRATA_PREFILL_LM_TOKENS` は target super-chunk size、`STRATA_PREFILL_LM_FORCE` は短い prompt の下限条件に関係し、どちらも margin 値を上書きしない。CLI 等も margin 自体の優先設定にはならないが、VRAM の空き量や super-chunk 条件を変えれば fit 結果には影響する（`engine/src/prefill/prefill.cpp:8088-8100, 8235-8244, 8254-8272`）。

## 実行時の詳細

`lm_margin_bytes()` 内の `static const int64_t explicit_v` が、最初に margin を求めた時点の環境値を一度だけ読み取る。その後は同じプロセス内で環境変数を変更しても再読込しない。一方、未設定時の fallback を選ぶ `by_default` 引数は呼び出しごとに渡される（`engine/src/prefill/prefill.cpp:8113-8119`）。

fit 判定では `cudaMemGetInfo()` の空き byte 数から margin を引いた `room` を作り、候補 super-chunk の必要量が収まるまで chunk 単位で縮小する。設定値が大きいほど採用可能な super-chunk が小さくなり、最小候補すら収まらないと layer-major 準備を失敗させる。未設定時に使う 512 MiB は `by_default` の場合、96 MiB は明示的に layer-major が選択された場合の値である（`engine/src/prefill/prefill.cpp:8249-8285`）。

現在の checkout では `prefill_layer_major_default()` が常に false なので、`by_default == true` の経路（512 MiB）は通常の default resolver からは到達しない。small-card 経路が layer-major を自動選択するときも環境に明示的な `"1"` を設定してから選択するため、`lm_env_explicit()` は true となり、unset 時の fallback は 96 MiB 側になる（`engine/include/strata/core/sm120_series.hpp:184-192`; `engine/src/program/generate.cpp:12584-12590`; `engine/src/prefill/prefill.cpp:8082-8086, 9660-9662`）。

## ログと測定値

この変数専用の値表示や無効値警告はない。layer-major が選択され、必要な super-chunk が収まらない場合、理由として空き MiB・最小 super-chunk の token 数・必要 MiB・使用 margin MiB を含む `no VRAM for a super-chunk on CUDA...` が作られ、stderr に `strata prefill: layer-major off for this prompt: ...` として出る。prompt ごとの辞退理由は同じ理由について重複を抑制し、長い prompt の辞退が続く場合は 16 回ごとに継続ログも出す。layer-major 準備が失敗した通常の prompt はその後 `run_impl()` に進む（`engine/src/prefill/prefill.cpp:8273-8285, 9693-9705`）。

`docs/DETAILS.md` にはこの margin 変数固有の説明や測定値はない。同資料で layer-major に触れる箇所（`docs/DETAILS.md:1317-1320`）は別の選択機能が layer-major 経路では使われないという記述であり、この margin の測定根拠にはならない。

## 根拠

- `engine/src/prefill/prefill.cpp:8113-8119` — 環境変数の唯一の読み取り、変換、fallback。
- `engine/src/prefill/prefill.cpp:8249-8285` — VRAM margin の適用、fit と不足理由の生成。
- `engine/src/prefill/prefill.cpp:8166-8234, 9657-9705` — 適用条件、辞退、ログ、chunk-major への fallback。
- `engine/include/strata/core/sm120_series.hpp:184-192` — layer-major の現行 default resolver。
- `engine/src/program/generate.cpp:12538-12612` — small-card prompt 経路での layer-major 切替と関連条件。
