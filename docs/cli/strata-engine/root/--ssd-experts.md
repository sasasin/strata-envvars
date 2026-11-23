# `--ssd-experts`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（`strata` の root 引数 parser） |
| オプション | `--ssd-experts` |
| 別名 | なし |
| 値 | 取らない flag |

## 役割

expert の大容量 RAM arena を使わず、expert を pack 内のファイルから読む GPU+SSD / CPU+SSD 経路を選びます。parser は `mmap_experts` を有効にし、resident CPU copy / pin / soft と resident budget を無効化します。構造体の説明では、大きな host expert arena を確保せず、上限付き pinned DMA bounce/prefetch ring を使うモードとされています（`engine/src/program/generate.cpp:890-892,4231-4236`）。

## 使い方

```sh
# pack を指定して prompt token を渡し、expert file tier を使って生成する
strata generate --pack /path/to/pack --tokens "1,2,3" --ssd-experts
```

`--pack` と `--tokens` は `strata generate` の usage に示された通常の入力です（`engine/src/program/generate.cpp:1206-1212`）。

## 値と既定値

- 値・別名はありません。parser は引数と一致したときに `ssd_experts = true` にします。省略時は `Options::ssd_experts` の初期値 `false` です（`engine/src/program/generate.cpp:890-892,4231-4236`）。
- 重複指定の専用 validation はありません。繰り返しても同じ flag を true にします。
- `--ssd-experts=value` のような値付き形式は登録されていません。直後に別の値を置くと、それは別引数として処理され、未知の引数なら usage を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:3837-3842,4231-4236,4263-4268`）。

## 実行時の動作

`--ssd-experts` が指定されると `mmap_experts` が有効になり、resident CPU expert copy、pin、soft と resident budget がクリアされます。`mmap_experts` の実行経路では expert source を開き、開けなければエラーを stderr に出して終了コード 1、開ければ mmap 経由で expert file tier を使う旨を stderr に出します（`engine/src/program/generate.cpp:4231-4236,8550-8576`）。pack に `experts.bin` がない native pack では GGUF shard を source として扱う分岐もあります（`engine/src/program/generate.cpp:8550-8557`）。

SSD-only 指定では `FileExpertSource::set_unbuffered` に `force=true` が渡されます。Windows では `FILE_FLAG_NO_BUFFERING`、Linux では `O_DIRECT` でファイルを開き、成功時にその状態を stderr に報告します（`engine/src/program/generate.cpp:8583-8587`; `engine/src/core/expert_source.cpp:2766-2817,2842-2852`）。この直接 I/O の初期化が失敗しても、呼び出し側は戻り値を確認して「file cache 経由」と理由を stderr に出すだけで、ここでは起動を中止しません。Windows/Linux 以外では `set_unbuffered` が file cache 経由と報告して false を返します（`engine/src/core/expert_source.cpp:2800-2817,2842-2864`; `engine/src/program/generate.cpp:8583-8587`）。

## 適用条件と副作用

- このフラグ単独では SSD 上のファイルを変更する処理は確認できません。expert source の pack ファイルを開き、プラットフォームとファイルシステムが対応する場合は direct/unbuffered I/O で読みます。direct open に失敗した場合や対応外 platform では OS の file cache 経由になります（`engine/src/program/generate.cpp:8550-8587`; `engine/src/core/expert_source.cpp:2766-2817,2842-2864`）。
- `--ram-experts-gb 0` と `--resident-budget-gib 0` も parser 上で同じ `ssd_experts` / file-source 状態を設定します（`engine/src/program/generate.cpp:4237-4244`）。一方、正の budget は resident copy と budget を設定しますが、それ以前に true になった `ssd_experts` を明示的には false に戻しません。resident 系の他 option もそれぞれ状態を設定するため、これらと併用した場合は引数順により複合状態になります。互いに排他的な設定として併用する場合の意図・保証はソースから確認できません（`engine/src/program/generate.cpp:4216-4252`）。
- `--ssd-experts` の後に `--ram-experts-gb N`（N > 0）を置くと budget と resident copy は設定されても `ssd_experts` は true のままです。逆順なら後続の `--ssd-experts` が budget と resident copy を消します。順序依存を避けるため、両モードの指定を重ねない使い方が明確です（`engine/src/program/generate.cpp:4231-4252`）。
- SSD-only 時は routing-aware prefetch の既定深度を 2 にする条件にも `ssd_experts` が使われます。ただし `STRATA_IO_PREFETCH_DEPTH` が正ならその値が優先されます（`engine/src/program/generate.cpp:10245-10249`）。

## 出力とエラー

- file expert source を開けない場合、stderr にエラーを出し、RAM fallback 中の特別な再試行経路でなければ終了コード 1 になります（`engine/src/program/generate.cpp:8560-8572`）。
- direct I/O の開始に失敗した場合は原因を含む file-cache fallback の理由が stderr に出ます。対応外 platform では `through the file cache (no unbuffered reads on this platform)` と報告されます（`engine/src/core/expert_source.cpp:2773-2805,2842-2864`; `engine/src/program/generate.cpp:8583-8587`）。
- 未知の余分な引数は usage を含む stderr 出力と終了コード 2 になります（`engine/src/program/generate.cpp:4263-4268`）。

## 根拠

- `engine/src/program/generate.cpp:890-892` — option state と SSD-only mode の説明。
- `engine/src/program/generate.cpp:4231-4252` — flag parser、値なしの受理、関連 budget option との state interaction。
- `engine/src/program/generate.cpp:8550-8587` — expert file source の選択、open failure、direct I/O の呼び出しと診断出力。
- `engine/src/program/generate.cpp:10245-10249` — SSD expert 経路での prefetch depth 条件。
- `engine/src/core/expert_source.cpp:2766-2817,2842-2864` — Windows/Linux の direct open、失敗時 fallback、対応 platform 外の動作。
