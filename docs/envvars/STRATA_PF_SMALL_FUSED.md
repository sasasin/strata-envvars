# `STRATA_PF_SMALL_FUSED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

小さい expert cache 用の prefill 経路が選ばれたとき、その MMQ buffer layout の中でも native fused expert kernels を使うかを切り替える。未設定または `0` 以外の先頭文字なら fused kernels を許し、先頭文字が `0` ならこの経路で fused kernels を止めて MMQ kernels を使う。これは小さい cache 向け経路の選択自体を有効化する変数ではなく、その経路が成立した後の fused-kernel override を選ぶ変数である（`include/strata/prefill/pf_fused_override.hpp:26-29`、`src/program/generate.cpp:11691-11712`）。

この override はプロセス共通の atomic 値として fused prefill 側から参照される。値 `0` は fused kernels の選択を拒み、値 `2` は MMQ の layout と ring を保ったまま、既存の card / format 判定が許す fused kernels を使う指定である（`include/strata/prefill/pf_fused_override.hpp:1-18`、`src/prefill/moe_fused.cu:712-729`、`src/prefill/moe_fused_iq.cu:2901-2908`、`src/prefill/prefill.cpp:728-740`）。

## 値と判定

実行時の参照箇所では `std::getenv` の結果を `small_card_kernels_on` に渡し、`env != nullptr && env[0] == '0'` だけを無効条件にする。文字列全体の比較、数値変換、空白除去、大文字小文字変換、範囲検査はない（`include/strata/prefill/pf_fused_override.hpp:29`、`src/program/generate.cpp:11712`）。

| 条件 | unset | fused kernels を許す値 | fused kernels を止める値 |
|---|---|---|---|
| MMQ を含む build で小さい cache 経路が成立 | on（関数は `true`） | 空文字、`1`、`true`、`false`、` 0`、`0anything` 以外の文字列 | `0`、`0anything`、`00`、`0.0` など先頭文字が `0` の文字列 |
| `STRATA_PREFILL_FUSED` が定義され `STRATA_PREFILL_MMQ` が未定義の own-only build | build 判定で on | 指定値によらず on | 該当なし。この build は MMQ に戻せないため、`own_only_build()` が真なら環境変数を評価せず override `2` を設定 |
| HIP build | 該当経路に入らず、この変数を読まない | 該当なし | 該当なし |

判定は文字列の先頭 1 文字だけを見る。従って空文字は設定済みでも on、`false` も on、`0anything` は off、先頭に空白がある ` 0` は on になる。大文字小文字や文字列の数値としての妥当性は関係しない（`include/strata/prefill/pf_fused_override.hpp:29`、`src/program/generate.cpp:11696-11712`）。

## 有効になる条件

- `serve` の prefill chunk 計画で `chunk > 0` かつ `o.prefill_auto` が真であること。明示数値の `--prefill N` はこの判定を通らない。実際の `o.prefill_auto` が前段で無効化された場合も適用されない（`src/program/generate.cpp:11667-11673`、`src/program/generate.cpp:11691-11695`）。
- 単一 GPU 経路であること（`!multi_gpu` かつ `stages.empty()`）、`STRATA_PF_SMALL` が未設定または先頭文字が `0` 以外であること（`src/program/generate.cpp:11691-11699`）。`STRATA_PF_SMALL=0...` はこの小さい cache 経路全体を無効にする。
- `small_card_prompt_path` の判定で HIP ではなく、`STRATA_DEFAULTS=026` 相当の `v026` でもなく、expert layout が native pack で、default chunk が正で 8,192 未満であること（`include/strata/core/sm120_series.hpp:142-165`、`src/program/generate.cpp:11705-11707`）。`STRATA_DEFAULTS` は `026`、`0.2.6`、`v0.2.6` の完全一致を一度だけ読む（`include/strata/core/defaults_026.hpp:21-30`）。
- `STRATA_PF_FUSED` がユーザー指定の非空値として存在しないこと。own-only build が build 自身で設定した値はユーザー指定として扱わない（`include/strata/core/sm120_series.hpp:149-165`、`include/strata/prefill/own_only_switches.hpp:59-73`、`src/program/generate.cpp:11701-11707`）。
- `STRATA_PREFILL_LAYER_MAJOR` がユーザー指定されても fused-off 側の判定は残るが、layer-major walk は自動では有効化されない。そのため、この環境変数は fused-kernel override に作用し得る一方、walk を自動で選ぶ条件とは別である（`include/strata/core/sm120_series.hpp:149-165`、`src/program/generate.cpp:11701-11718`）。
- 条件を満たした後でも native fused kernel が使えるかは既存の device・format 判定に従う。`STRATA_PF_SMALL_FUSED` は未対応の card / format に kernel を追加しない（`src/prefill/moe_fused.cu:683-708`、`src/prefill/moe_fused_iq.cu:2891-2928`）。

## 実行時の詳細

`serve` は expert cache を sizing した後、default prompt chunk を計画する。小さい cache 用 helper は、単一 CUDA card・native pack・default chunk が 8,192 未満などの条件で `fused_off` を返し、fused layout を避ける経路を選ぶ（`include/strata/prefill/pf_fused_override.hpp:3-5`、`include/strata/core/sm120_series.hpp:142-165`）。このとき `STRATA_PF_SMALL_FUSED` を直接 `getenv` し、own-only build なら値を見ずに override `2`、それ以外では on 判定なら `2`、off 判定なら `0` を atomic に保存する（`src/program/generate.cpp:11709-11712`）。

override `0` では fused prefill selection が拒否され、fused ring も使わないため、この layout の該当 expert 計算は MMQ 側に残る。override `2` では fused layout / fused ring は使わず、card と format の既存規則が対象にする箇所で fused kernels を許す（`include/strata/prefill/pf_fused_override.hpp:6-8,21-29`、`src/prefill/prefill.cpp:728-740`、`src/prefill/moe_fused.cu:712-729`、`src/prefill/moe_fused_iq.cu:2901-2908`）。

環境値の読み取りは `generate.cpp` のこの計画分岐で直接行われ、対象変数用の `static` cache はない。ソース上、この判定は token ごと・request ごとの読み直しではなく serve の chunk 計画時に置かれている。プロセス実行中に環境を変更した場合に計画や override を再設定する経路、およびこの変数の子プロセスへの転送は確認できない（`include/strata/prefill/pf_fused_override.hpp:3-5,16-18`、`src/program/generate.cpp:11691-11712`）。

新しい layout の chunk scan が `0` になった場合は override を `-1` に戻し、必要なら自動設定した `STRATA_PREFILL_LAYER_MAJOR` を解除して既定経路を再 scan する（`src/program/generate.cpp:11720-11735`）。

## ログと測定値

小さい cache 用経路が成立すると、設定値そのものではなく選択した path と chunk を stderr に出す。chunk が確保できた場合の文字列は `strata serve: small expert cache: the default prompt path would read in chunks of %lld tokens (under %lld), so prompts are read the way that suits a card with little memory%s (chunk %lld tokens); STRATA_PF_SMALL=0 keeps the default path, STRATA_PF_FUSED / STRATA_PREFILL_LAYER_MAJOR set by hand win`。unfused layout の buffer がどこにも収まらない場合は override を戻し、`strata serve: small expert cache: the unfused prompt path does not fit here; the default path stays (chunk %lld tokens)` を出す。これらのログには `STRATA_PF_SMALL_FUSED` の値や fused / MMQ の内訳は表示されない（`src/program/generate.cpp:11724-11741`）。

`docs/SETTINGS.md:341` は NVIDIA / AMD の on/off 候補として列挙するだけで、適用条件や測定値の説明はない。コードコメントには小さい cache 経路自体の条件付き測定記述があるものの、`STRATA_PF_SMALL_FUSED` の on/off 差を比較した測定は確認できないため、この変数による速度・出力差は記載しない（`include/strata/core/sm120_series.hpp:142-151`）。

## 根拠

- `include/strata/prefill/pf_fused_override.hpp:1-29` — override の状態値と対象変数の値判定。
- `include/strata/core/sm120_series.hpp:142-165` — 小さい cache 用経路の条件、chunk 閾値、他の設定との関係。
- `src/program/generate.cpp:11691-11741` — serve 側の gate、環境値の読み取り、override 設定、fallback とログ。
- `include/strata/prefill/own_only_switches.hpp:18-24,41-73`、`src/prefill/prefill.cpp:204-235` — MMQ なし build と build が設定する fused switches。
- `src/prefill/moe_fused.cu:712-729`、`src/prefill/moe_fused_iq.cu:2891-2908`、`src/prefill/prefill.cpp:728-740` — override が fused kernel selection と ring に反映される箇所。
- `include/strata/core/defaults_026.hpp:21-30`、`docs/SETTINGS.md:341` — `STRATA_DEFAULTS` の判定と設定一覧との照合。
