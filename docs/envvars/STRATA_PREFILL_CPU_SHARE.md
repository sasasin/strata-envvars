# `STRATA_PREFILL_CPU_SHARE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有ソースを対象とし、外部ライブラリや GPU ドライバーの環境変数動作は含めない。

## 役割

prompt prefill 中、GPU が PCIe 経由で読み込む非 resident expert の一部を、decode 用 CPU pool に計算させる割合を指定する。CPU pool が prompt 処理中に空いていて、expert のデータを CPU から安定して読める場合に使われる。値 `0` は share を無効にし、expert を GPU 側で処理する。`auto` は CPU と GPU の処理時間を測って割合を選ぶ。

環境値は `src/prefill/prefill.cpp` の `cpu_share_explicit()` が `static const double` にキャッシュする。最初の評価後にプロセス内で環境を書き換えても、この値は再読込されない。

## 値と判定

環境変数の文字列全体を一般的な真偽値として解釈するものではない。完全一致の小文字 `auto` だけが測定モードになり、それ以外は `std::atof()` で数値変換し、`std::clamp(..., 0.0, 1.0)` で 0〜1 に制限する。

| 値 | 判定 |
|---|---|
| 未設定 | 通常は 0。後述の既定有効条件を満たして既定 share が armed された場合は `auto` と同じ測定モード |
| `auto` | 完全一致の場合のみ測定モード。大文字小文字や前後の空白を含む別表記は一致しない |
| 数値 | `atof` が読む数値を 0〜1 に clamp した固定割合。例: `0.4` は 0.4、`2` は 1、`-1` は 0 |
| 空文字、数値に変換できない文字列 | `atof` の結果が 0 になり share 無効 |
| 数字の後ろに文字が続く文字列 | `atof` が先頭の数値部分を変換する。たとえば `0.4extra` は 0.4 |

固定割合では、各 layer の非 resident streamed expert 数に割合を掛けて `llround` し、CPU が安定した blob を取得できる候補数を上限として CPU に割り当てる。したがって、割合どおりの個数を常に CPU が処理するとは限らない。根拠: `src/prefill/prefill.cpp:184-197,3256-3287`。

## 有効になる条件

- 既定 share は、HIP 系 macro (`STRATA_USE_HIP` または `STRATA_HIP_GFX906`) が定義されていないビルドでのみ自動設定される。HIP では unset の既定値は share 無効だが、明示設定値は `cpu_share_explicit()` から引き続き使われる。根拠: `src/prefill/prefill.cpp:1960-1972`。
- `generate` の既定有効経路は単一 GPU、CPU pool 使用、batch slots なし、GPU expert cache に全 expert が載っていないこと、メモリ判定を通ることが条件。`serve` でも既定有効は単一 GPU・stage なし・batch slots なし・cache に未収容 expert があり、メモリ判定を通る場合に限られる。明示値は既定有効条件と別に扱われる。根拠: `src/program/generate.cpp:7281-7289,13154-13159`。
- メモリ不足判定は既定動作だけを止める。Strata は利用可能 RAM が share 用 buffer と 3 GiB の合計未満、Windows の利用可能 commit が buffer と 4 GiB の合計未満、または CPU が読む file-page expert を保持する RAM が不足する場合に既定 share を armed しない。環境値が未設定なら理由を stderr に表示する。明示値が `0` 以外ならその値を保持して警告する。`0` は警告せず無効化する。根拠: `include/strata/prefill/share_rules.hpp:21-59`, `src/program/generate.cpp:7202-7229`。
- default の適用可能性を調べる際、GPU cache に全 expert がある場合は「取る expert がない」として既定有効にしない。`auto` など明示した値ではこの既定判定を強制条件にはしない。根拠: `include/strata/prefill/share_rules.hpp:15-18`, `src/program/generate.cpp:7282-7289`。
- 実際の chunk では pool を確保でき、全 expert streaming の chunk ではなく、source があり、CPU share buffer が失敗で無効化されておらず、native CPU expert format が使えることが必要。layer split では pool を同時に使える stage は一つに制限される。根拠: `src/prefill/prefill.cpp:2341-2351,3137-3147`。
- share が有効な場合の chunk 上限は別変数 `STRATA_PREFILL_CPU_SHARE_MAX` が決める（未設定 3072、最小 1024）。`STRATA_PREFILL_STREAM_MIN` が明示されている場合はそちらが優先して全 expert streaming の境界を決める。未設定の share を既定有効にした場合、別変数 `STRATA_PREFILL_CPU_SHARE_MAX` も未設定なら測定範囲に合わせ上限は 1024。根拠: `src/prefill/prefill.cpp:164-167,198-208`。

## 実行時の詳細

`Prefill::arm_cpu_share()` は share を適用できる場合に chunk の streaming 境界を更新する。prompt chunk がその境界以上なら `stream_all` 経路に入り、CPU share は使われない。下回る chunk では、routed ID の集計後に非 resident expert を選び、CPU pool に一部の expert rows を計算させる。GPU 側は残りの expert を処理し、CPU rows を combine 前に GPU にコピーする。CPU が使うのは pinned blob に限らず、arena や mapped expert file pages など安定して参照できるデータを含む。根拠: `src/prefill/prefill.cpp:164-167,2341-2351,3256-3287,3411-3432,4018-4035`。

`auto` は適格 layer の CPU/GPU 両方の所要時間を計測し、割合を両者の完了時間が釣り合う値に更新する。また share あり／なしの layer を最初に交互に比較し、以降も一定間隔で比較を続け、share 側が遅い場合は通常の layer で CPU に割り当てない。値の割合を選ぶ測定と、share 自体が速いかを判定する測定は別の処理である。根拠: `src/prefill/prefill.cpp:817-834,3149-3167,3411-3429,4018-4028`。

CPU が必要な pinned buffer を確保できなかった場合、その実行中は share を無効にし、GPU が全 expert を処理する。リクエスト自体はこの失敗だけでは失敗させない。別の CPU rows/scale allocation 経路ではエラーを返す分岐もある。根拠: `src/prefill/prefill.cpp:3139-3147,3173-3180,3388-3405`。

起動時には、既定 share が有効なら `prefill: the CPU share is ON by default ...`、メモリ条件で既定無効なら理由付きの `strata: the CPU prefill share is not armed by default: ...` が stderr に出る。明示値をメモリ警告下で保持する場合は `strata: WARNING STRATA_PREFILL_CPU_SHARE=... is set and kept, but ...` が出る。生成結果について、CPU と GPU は異なる activation format で計算するため最下位 bit が変わり得る。`auto` は timing により layer ごとの配分が変わる場合もある。根拠: `src/prefill/prefill.cpp:1960-1967,3415-3432`, `src/program/generate.cpp:7221-7228`。

## 文書との照合

`docs/DETAILS.md:1597-1620` は 0.1.41 で一部 CUDA 実行を既定有効にしたこと、0.1.42 でメモリ不足時には既定動作を外すこと、明示値の扱い、結果がわずかに異なり得ることを説明している。同節の冒頭には「set しない限り off」とする以前の記述も残るが、後続の 0.1.41/0.1.42 の記述と現行 `arm_cpu_share()` / 呼び出し条件が示す現在の動作を優先した。資料中の性能値は Strata が記載した特定環境での測定であり、本調査で再測定していない。

## 根拠

- 値の parse、既定値、chunk 上限: `src/prefill/prefill.cpp:164-208`
- default / explicit の armed 処理: `src/prefill/prefill.cpp:1959-1972`
- share の実行条件・CPU/GPU への expert 割り当て: `src/prefill/prefill.cpp:2341-2351,3137-3167,3256-3287,3411-3432,4018-4035`
- 呼び出し側の既定条件とメモリ判定・警告: `src/program/generate.cpp:7202-7229,7281-7289,13154-13159`, `include/strata/prefill/share_rules.hpp:15-59`
- 設計説明と測定値の出典: `docs/DETAILS.md:1597-1620`
