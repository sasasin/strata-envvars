# `--resident-experts`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--resident-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GPU の expert cache にない experts を起動時にホスト RAM へ常駐させ、回答中にファイルから読み直す場面を減らす低 RAM 向けモードです。全 complement が RAM に収まらない場合も、profile で順位付けされた hot experts を可能な範囲で RAM に置き、残りは mmap したモデルファイルから読みます。CUDA/HIP の実装では mmap 読み込みだけに戻る soft fallback も行います。オプションは `--mmap-experts`、`--resident-cpu-experts`、4 GiB の headroom、page-lock を組み合わせます（`engine/src/program/generate.cpp:877-880,4221-4228`）。

## 使い方

```sh
# pack と静的 expert profile を指定し、resident RAM mode で実行する
strata --pack /path/to/pack --expert-profile /path/to/expert-profile.bin --resident-experts --tokens '1,2,3'
```

この例の pack、profile、token は説明用の値です。`--tokens` などの生成入力は別の引数で指定します。

## 値と既定値

- フラグ自体に値は不要で、明示したとき `mmap_experts`、`resident_cpu_experts`、`resident_pin`、`resident_soft` を有効にし、resident headroom を 4 GiB にします（`engine/src/program/generate.cpp:4221-4228`）。未指定時はこのフラグ由来の resident 設定を行いません（各 bool の初期値は `engine/src/program/generate.cpp:874-886`）。
- `STRATA_RESIDENT_PIN=0` のときコピーを page-locked にせず、それ以外（未設定を含む）では page-locked を要求します（`engine/src/program/generate.cpp:4224-4226`, `engine/include/strata/core/resident_ram_copy.hpp:11-15`）。ドライバーが page-lock できない場合の実際の lock 状態は起動時の報告に反映されます（`engine/src/program/generate.cpp:12196-12202`）。
- `STRATA_RESIDENT_HEADROOM_GIB` が `atof` で 0 以上になる値なら、4 GiB の headroom をその GiB 値で置き換えます。条件を満たさない値はこの分岐では採用されません（`engine/src/program/generate.cpp:4224-4228`）。`--ram-keep-gib` または `STRATA_RAM_KEEP_GIB` がより大きい headroom を要求し、かつ `STRATA_RESIDENT_HEADROOM_GIB` が有効値でなければ、そちらまで headroom を引き上げます（`engine/src/program/generate.cpp:4277-4285`）。
- 重ねて指定した場合も同じフラグ設定を繰り返します。回数を数える処理や重複指定エラーは parser にありません（`engine/src/program/generate.cpp:3842-3849,4221-4229`）。

## 実行時の動作

1. resident CPU copy を有効にすると `--mmap-experts` も有効になります。engine は pack の `experts.bin`、または対応 pack で experts が含まれる GGUF shard をファイル tier として開きます（`engine/src/program/generate.cpp:8621-8647`）。
2. GPU cache にない expert を特定し、静的 expert profile の順位を使って RAM copy を作ります。GPU cache が保持する expert と、layer split の各 stage cache が保持する expert は copy の対象から除かれます（`engine/src/program/generate.cpp:11908-11910,11933-11948,12077-12080`）。resident source の実装は cache complement を構築し、GPU cache が開いていること、全 slot の fill 完了、GPU 同期などを確認します（`engine/src/core/expert_source.cpp:3985-4003,4012-4024`）。
3. prefill が cache slot を借りる構成では、借用中に file から読み出される expert も RAM が許す限り copy に含めます（`engine/src/program/generate.cpp:11908-11931`; `engine/src/core/expert_source.cpp:4219-4232`）。resident mode では、GPU cache にない expert を一度 RAM にコピーし、decode や prompt 中にファイルから読み直さない設計です（`engine/src/program/generate.cpp:11747-11753`）。
4. 全 complement を headroom 内に収められない場合、`resident_soft` による二度目の試行で利用可能 RAM に合わせた予算を決め、profile 上位の expert を保持します。残りの expert はファイル tier を使い、警告を出します（`engine/src/program/generate.cpp:12079-12106`; `engine/src/core/expert_source.cpp:4040-4066,4133-4151`）。起動に成功したときは RAM に保持した GiB 数、page-lock 状態、GPU cache 数、および adaptive swap の状態を stderr に出します（`engine/src/program/generate.cpp:12196-12202`）。

## 適用条件と副作用

- resident CPU copy には `--mmap-experts` と静的 `--expert-profile` の両方が必要です。このフラグは前者を自動設定しますが、profile は自動生成しません。条件を満たさない場合は `--resident-cpu-experts requires --mmap-experts and a static --expert-profile` を stderr に出して終了コード 2 で拒否します（`engine/src/program/generate.cpp:4870-4873`）。
- resident RAM はモデルファイルの expert bytes をコピーするため、使えるホスト RAM を消費します。既定では 4 GiB を headroom とし、OS の利用可能 RAM（Windows では commit 容量も）に合わせて予算を調整します。page-lock はドライバーが許す場合に使われ、設定や環境により pageable または別の lock 状態になります（`engine/src/core/expert_source.cpp:4044-4066,4190-4217`; `engine/src/program/generate.cpp:12196-12202`）。
- まず全量 resident を試み、それが失敗した soft mode では可能な分だけに縮小します。縮小試行でも expert を一つも保持できないなどの条件では `--mmap-experts` 相当の file tier に戻り、警告を出して続行します（`engine/src/core/expert_source.cpp:4145-4147`; `engine/src/program/generate.cpp:12092-12106,12203-12217`）。そのため指定しても全 experts の RAM 常駐は保証されません。
- `--shared-expert-arena` は resident arena 用であり、`--resident-experts` が設定する `--mmap-experts` と併用できません。併用時は明示的なエラーを出して終了コード 2 になります（`engine/src/program/generate.cpp:4866-4869`）。
- `--adapt-async` を指定する場合、resident RAM mode が必要条件の一つです。resident が使えないときは async を無効にして blocking adaptive tier に切り替えます（`engine/src/program/generate.cpp:11801-11811`）。
- SYCL engine にも同名の値なし parser と resident 設定があります（`engine/sycl/src/program/generate.cpp:2184-2193`）。同 parser も resident CPU copy に `--mmap-experts` と静的 profile を要求し（`engine/sycl/src/program/generate.cpp:2339-2342`）、resident 全量が収まらない場合に縮小を試して mmap fallback を警告します（`engine/sycl/src/program/generate.cpp:7098-7107,7138-7151`）。上記の詳細な RAM/file-source の挙動は CUDA/HIP 側の実装位置を示しています。

## 出力とエラー

- 不明な引数は `unknown argument: <引数>` と usage を stderr に出して終了コード 2 です（`engine/src/program/generate.cpp:4268-4273`）。
- resident の構築・利用可能メモリ確認に失敗して soft fallback も成立しない場合は `CPU expert residency: ...` を stderr に出し、終了コード 1 になります。一方、soft fallback の対象では mmap 継続の警告を出して処理を続けます（`engine/src/program/generate.cpp:12203-12217`; `engine/src/core/expert_source.cpp:3991-4003,4047-4053`）。
- `--resident-experts` の分岐自体は出力ファイルを作る処理を行いません。expert bytes を起動時に RAM へ読み込み、fallback 時は pack/GGUF のファイル tier から読みます（`engine/src/program/generate.cpp:8621-8647,11747-11753`）。

## 根拠

- `engine/src/program/generate.cpp:874-886` — resident 関連 option state と初期値。
- `engine/src/program/generate.cpp:1486-1496,4221-4228` — usage 表示および parser の設定、関連環境変数。
- `engine/src/program/generate.cpp:4277-4285,4866-4873` — RAM headroom の優先関係と起動時 validation。
- `engine/src/program/generate.cpp:8621-8647,11908-11931,11933-11948,12077-12106,12196-12217` — file source、resident copy の適用、soft fallback、出力・失敗経路。
- `engine/src/core/expert_source.cpp:3985-4003,4040-4066,4133-4151,4190-4217` — resident complement の前提確認、予算調整、profile 順の保持、headroom 検査。
- `engine/include/strata/core/resident_ram_copy.hpp:11-15` — `STRATA_RESIDENT_PIN` の解釈。
- `engine/sycl/src/program/generate.cpp:2184-2193,2339-2342,7098-7107,7138-7151` — SYCL parser、validation、resident/fallback 経路。
