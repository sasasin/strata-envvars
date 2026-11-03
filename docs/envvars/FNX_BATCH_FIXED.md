# `FNX_BATCH_FIXED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の複数 lane batched decode で、各 lane に次の window 用の draft を何個割り当てるかを固定します。`-1` は既定の planner を使い、`0` 以上では各 lane に同じ個数を割り当てます。ただし実際の個数は、その lane が提供できる数までです。コードコメントでは sweep 用とされています。

この設定を読むのは `src/split/src/batch.cpp` の `BatchDecoder` 構築時だけです。sFNX では `--batch` が 2 以上で、`FNX_BATCH_DRAFTS` が off でないときに decoder が作られます。開発・計測用 `fnx_run bdecode` も同じ decoder を使います。通常の Strata engine 全般に適用される設定ではありません。sFNX 自体は `STRATA_BUILD_SPLIT=ON` で有効にする Linux CUDA / HIP 向けの optional build です。

## 値と判定

値は `env_int("FNX_BATCH_FIXED", -1)` で読み取られます。`env_int` は未設定時だけ既定値を返し、設定値は符号付き base-10 整数として全体を parse します。先頭の `+` / `-` と数字列は受け付けます。空文字、空白、末尾の文字、整数でない文字列、`long long` の範囲外は無効で、`FNX_BATCH_FIXED: '<値>' is not a whole number` の例外になります。

parse 後は `-1` または `0..15` が許されます（`MAXT` は 16）。それより小さい値、または通常の整数範囲で 15 より大きい値は `FNX_BATCH_FIXED: -1 (the plan) or 0..15` の例外になります。

| 値 | 動作 |
| --- | --- |
| 未設定 / `-1` | `choose_rows(...)` による planner の配分を使う |
| `0` | 各 lane の配分数を 0 にする |
| `1..15` | 各 lane の配分数を `min(設定値, その lane の提供可能数)` にする |
| 不正値 / 許容範囲外 | decoder 構築時に例外 |

空文字は未設定扱いではなく不正値です。`MAXT` は `src/split/src/model.hpp:43` に定義されています。なお、range 判定は実装上 `fixed + 1 > MAXT` を使うため、`long long` 最大値では符号付き加算のオーバーフローが起こり得ます。その極端な値に対する結果は C++ 上未定義であり、保証された fallback はありません。

## 有効になる条件

- sFNX server は `--batch` が 2 以上で、`FNX_BATCH_DRAFTS` が `0` でない場合に `BatchDecoder` を構築します。`FNX_BATCH_DRAFTS` は未設定時に MTP draft mode、`1` で MTP draft mode、`lookup` で lookup-only mode、`0` で off です（完全一致）。設定を `0` にすると sFNX ではこの変数を読む decoder 自体が作られません。
- `sfnx` は `--serve` で起動する server で、複数 lane の実行時に `BGEN` / `BGENI` request を処理します。`--batch` が 1 の場合は batch request を拒否し、decoder も作りません。
- `fnx_run bdecode` は `FNX_BATCH_DRAFTS` が off なら `bdecode: set FNX_BATCH_DRAFTS (lookup or 1)` を stderr に出して status 2 で終了します。そうでなければ同じ `BatchDecoder` を構築します。
- backend/build の入口は `STRATA_BUILD_SPLIT` です。CMake は Linux CUDA または HIP の split engine を対象としており、HIP build macro は `FNX_HIP` を定義します。この macro は同じ constructor 内の `FNX_BATCH_DRAFT` の既定値には影響しますが、`FNX_BATCH_FIXED` の parse と planner 分岐は共通です。
- この変数を読む実装は `src/split/` 内にあります。CUDA/HIP の `FNX_BATCH_DRAFTS` 分岐などの他設定は decoder の利用条件・draft mode に関わりますが、`FNX_BATCH_FIXED` の数値判定や値を上書きする CLI option は確認できません。

## 実行時の詳細

値は `BatchDecoder` の構築時に一度読み、メンバー `fixed_` に保持します。sFNX では server 初期化時に decoder を作り、以後の window は保存済みの `fixed_` を使います。プロセス起動後に環境値を変えても、作成済み decoder には反映されません。新しく decoder を構築する場合はその時点の環境値を読み直します。

各 window で draft offer と各 lane の `avail` を計算した後、`fixed_ >= 0` なら各配分を `min(fixed_, avail)` に設定し、planner 呼び出しを飛ばします。`fixed_ == -1` なら lane の held layout、推定コスト、capture cost を使う `choose_rows` の planner 経路になります。上限は lane ごとの提供可能数で、context の残り、lookup draft 数または MTP chain room などから計算されます。

固定配分は `FNX_BATCH_TRACE` が有効なら既存の `batch plan:` stderr 行に `d=<配分数>` として見えます。`FNX_BATCH_FIXED` 自体について専用ログはありません。`0` の MTP mode では行に載せる draft 数は 0 ですが、MTP の先頭 draft を `shadow` として計算する処理は残ります。

不正な整数文字列や許容範囲外の値は decoder 構築時に例外になります。sFNX server の初期化時なら stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出し、status 1 で終了します。`fnx_run bdecode` では最上位 catch が stderr に `fnx_run: ...` を出し status 1 で終了します。

## 根拠

- 候補一覧にも名前があり、実際の読み取りは `src/split/src/batch.cpp:78` の 1 箇所。値の範囲、`fixed_` への保存、他の decoder 設定は `src/split/src/batch.cpp:64-85`。
- 整数の厳密な parse、未設定 fallback、parse error は `src/split/src/env.hpp:15-21,33-40`。
- planner を通る条件と固定配分は `src/split/src/batch.cpp:261-311`。`avail` の計算は `src/split/src/batch.cpp:268-285`。trace 行は `src/split/src/batch.cpp:312-324`。固定値 0 の MTP shadow 処理は `src/split/src/batch.cpp:329-357`。
- window の最大行数は `src/split/src/model.hpp:43`。
- sFNX の `--batch` と `FNX_BATCH_DRAFTS` による decoder 作成は `src/split/tools/sfnx.cpp:65-104,435-445`。複数 batch slot 時の window 呼び出しは `src/split/tools/sfnx.cpp:572-607`。
- split engine の optional build 条件は `CMakeLists.txt:2947-2948` と `src/split/CMakeLists.txt:4,25-29,92-117`。
- `FNX_BATCH_DRAFTS` の mode と既定値は `src/split/src/engine_common.cu:1020-1028`。sFNX の batch request 条件は `src/split/tools/sfnx.cpp:975-997`。
- 開発・計測用 `bdecode` の mode 判定、decoder 構築は `src/split/tools/fnx_run.cpp:646-670`。最上位の例外表示と status は `src/split/tools/fnx_run.cpp:1364-1373`。
- sFNX の起動時失敗表示と終了経路は `src/split/tools/sfnx.cpp:1027-1036,1040-1065,1086-1093`。
