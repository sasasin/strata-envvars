# `--mtp-hnorm`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンのトップレベル引数） |
| オプション | `--mtp-hnorm` |
| 別名 | なし |
| 値 | `pooled` または `stream` |

## 役割

MTP drafter が hidden residual を `pre_fc_norm_hidden.weight` で正規化する方法を選びます。`pooled` は既定の全 hyper-connection stream をまとめた RMS 正規化、`stream` は各 stream を独立に RMS 正規化します。後者は llama.cpp の qwen4exp MTP graph と同じ方式として実装されています（`src/program/generate.cpp:785-787,945-946`、`include/strata/core/mtp.hpp:59-62`）。

## 使い方

```sh
strata --native /path/to/model.native --mtp /path/to/mtp --spec 4 --mtp-hnorm stream
```

値は別引数で渡します。`--mtp-hnorm=stream` 形式は parser のオプション名との一致条件に合わず、未知引数として扱われます（`src/program/generate.cpp:2416-2424,2676-2683,2788-2792`）。

## 値と既定値

- 省略時は `pooled` 相当です。`Options::mtp_hnorm_stream` は `false` で初期化されます（`src/program/generate.cpp:785-787`）。
- `pooled` は明示しても既定動作と同じです。`stream` は内部フラグを有効にします（`src/program/generate.cpp:2676-2683`）。
- 大文字小文字を含め、受理値は `pooled` と `stream` の完全一致です。それ以外の値は stderr に `strata generate: --mtp-hnorm takes pooled or stream` を出して終了コード 2 で拒否されます（`src/program/generate.cpp:2676-2681`）。
- 値を省略すると `--mtp-hnorm needs a value` を stderr に出して終了コード 2 になります（`src/program/generate.cpp:2418-2420`）。
- 同じオプションを複数回指定した場合は parser が順に処理し、最後に指定した値が内部フラグに残ります（`src/program/generate.cpp:2416-2421,2676-2683`）。

## 実行時の動作

parser は `stream` のときだけ `mtp_hnorm_stream` を true にします。MTP 初期化ではこの値を `MtpDrafter::set_hnorm_per_stream` に渡し、drafter の最初の draft / prefill または graph capture より前に設定します（`src/program/generate.cpp:5455-5463`、`include/strata/core/mtp.hpp:59-62`）。

通常の draft forward では、`stream` の場合に `native_qsa_rms_norm_grouped` を使い、hidden 入力を `N` 列・`HC` グループとして正規化します。`pooled` では同じ入力に `HC * N` 列の weighted RMS を適用します（`src/core/mtp.cpp:908-915`）。Grouped kernel は各行を独立に正規化し、行番号 modulo `groups` に対応する gamma の slice でスケールします（`include/strata/kernels/native_qsa.hpp:24-27`）。

Prompt prefill の MTP pass も同じ設定を参照し、`stream` なら grouped RMS、そうでなければ全 `HCN` 列の row RMS を使います。その後はいずれの方式でも各 stream を `fc_hidden` projection に通します（`src/prefill/prefill.cpp:1846-1856`）。従って指定の効果は MTP の draft 計算に限られ、ターゲットモデル本体の正規化方式を切り替えるものではありません。

## 適用条件と副作用

- `--mtp-hnorm` 自体は MTP の有無を検査せず値を記録します。実際に適用されるのは MTP drafter が初期化・実行される場合です。MTP path (`--mtp`) がない場合、この値だけでは drafter をロードしません（`src/program/generate.cpp:2623,5455-5472`）。
- `--mtp` を指定しても `--spec` が 2 未満なら、エンジンは MTP を無視する旨を stderr に出して path をクリアします。その場合この設定による MTP 計算は行われません（`src/program/generate.cpp:5455-5462`）。
- `stream` は draft hidden の正規化とそれに続く drafter projection の入力を変えます。性能向上や生成結果の変化量はこの parser・呼び出し箇所からは保証できません。ファイルや環境変数を変更する処理は確認できません。
- Qwen3.6 family は通常 parser に入る前に専用 `qwen35::run` へ振り分けられます。このページは索引上の `strata-engine/root` scope を扱い、専用 parser における同オプションの対応状況・挙動は対象外です（`src/program/generate.cpp:2393-2407`）。

## 出力とエラー

無効値・値の欠落は上記のとおり stderr と終了コード 2 になります。認識されない引数は `unknown argument: ...` と usage を出して終了コード 2 です（`src/program/generate.cpp:2418-2420,2788-2792`）。このオプション単独で成功時に出力を行う箇所は確認できません。MTP model の load 失敗は別の一般的なエラー経路で stderr に理由を表示し、終了コード 1 になります（`src/program/generate.cpp:5472`）。

## 根拠

- parser、既定値、help 表示: `src/program/generate.cpp:785-787,945-946,2676-2683`
- 引数不足・未知引数: `src/program/generate.cpp:2416-2420,2788-2792`
- MTP 条件と setter 適用: `src/program/generate.cpp:5455-5472`
- draft 経路の RMS 分岐: `src/core/mtp.cpp:908-915`
- prefill 経路の RMS 分岐: `src/prefill/prefill.cpp:1846-1856`
- grouped RMS の gamma slice と row 単位動作: `include/strata/kernels/native_qsa.hpp:24-27`
- 専用 family path への早期 dispatch: `src/program/generate.cpp:2393-2407`
