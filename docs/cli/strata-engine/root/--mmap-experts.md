# `--mmap-experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main`（`origin/main` 追跡）で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--mmap-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

expert の供給元を、通常の resident arena から `FileExpertSource` に切り替えます。expert データを `experts.bin`、または対応する native pack ではモデル GGUF shard から読み、ファイルのマッピングと OS file cache を使います。GPU cache に載らない expert もファイル側から供給されます。これは主に expert 全体を resident arena として RAM に置けない場合の経路です。OS がファイルページを保持する量は環境に依存するため、このフラグ単独で使用 RAM が一定量に抑えられる保証はありません。

## 使い方

```sh
strata --native /path/to/model.gguf --pack /path/to/pack --mmap-experts --max-new 32
```

例では `model.gguf` と `pack` を実際の native model / pack のパスに置き換えます。engine の usage は `--pack DIR` を pack directory（既定 `pack/full`）として定義し、native model は `--native` で指定します（`src/program/generate.cpp:808-810,2500`）。

## 値と既定値

- 値を取りません。parser は引数が `--mmap-experts` と一致すると `mmap_experts = true` にします。parser 初期値は `false` です。別名や個別の値検証はありません（`src/program/generate.cpp:536,2753-2755`）。
- 明示しなくても Metal build では、Metal engine が GGUF shard を読む設定と合わせて `mmap_experts` を `true` にします（`src/program/generate.cpp:3422-3425`）。
- `--resident-experts` はこのフラグ相当の状態に加え、resident CPU copy / pin / soft fallback も有効化します。`--resident-budget-gib N` も resident CPU copy と pin を有効にして mmap 経路を選びます（`src/program/generate.cpp:2757-2776`）。

## 実行時の動作

- `mmap_experts` が true のとき、engine は `FileExpertSource` を開きます。`experts.bin` がある pack ではそのファイルを読み取り専用で map します。native pack に `experts.bin` がなく GGUF path が設定されている場合は、expert tensor の shard を map して必要な span を参照します（`src/program/generate.cpp:5707-5724`; `src/core/expert_source.cpp:1422-1432,1452-1519,1652-1732`）。
- 通常の expert 参照は resident complement に存在すれば RAM copy から、そうでなければ map / staging / 有効時の I/O prefetch 経由でファイル側から返されます（`src/core/expert_source.cpp:4561-4598`）。RAM copy はこのフラグ単独では作りません。`--resident-cpu-experts` 等を併用すると別途構築されます。
- `--shared-expert-arena FILE` とは併用できません。両方が有効な場合、初期検証で stderr にエラーを出し終了コード `2` で終了します（`src/program/generate.cpp:3040-3045`）。
- `--resident-cpu-experts` を使う場合は `--mmap-experts` と static `--expert-profile` が必須です。不足時は同じく終了コード `2` です。`--resident-experts` と `--resident-budget-gib` は mmap 状態を自動設定するため、このフラグを重ねて指定する必要はありません（`src/program/generate.cpp:2757-2776,3044-3047`）。
- `--resident-budget-gib` を使わない mmap 経路では `STRATA_UNBUFFERED_LOAD=1` は採用されず、stderr に無視した旨が出ます。予算指定時は file tier の unbuffered I/O を試み、利用可否を stderr に表示します（`src/program/generate.cpp:5725-5740`）。

## 適用条件と副作用

- 対象は索引で `strata-engine/root` としている `src/program/generate.cpp` の parser です。`strata-engine-dsv41` の同名オプションとは別 tool-id / parser scope です（索引 `docs/cli/README.md:1128-1135,1202,1353-1375`）。
- `experts.bin` を使う場合、ソースは読み取り専用で開き、ファイルサイズがロード済み expert layout の要求サイズに一致することを確認してから map します。サイズ不一致、open / stat / mapping 失敗はエラーになります（`src/core/expert_source.cpp:1422-1433,1452-1508`）。native pack の GGUF 経路では GGUF と layout の整合性を確認し、各参照 span が shard の範囲内か検査します（`src/core/expert_source.cpp:1657-1660,1718-1726`）。
- `FileExpertSource::open` が失敗すると engine はエラーを stderr に出し、終了コード `1` を返します。成功時は `experts via mmap (--mmap-experts; ...)` を stderr に出します（`src/program/generate.cpp:5719-5724`）。未知の引数は parser が usage と `unknown argument` を stderr に出し、終了コード `2` にします（`src/program/generate.cpp:2787-2792`）。
- map は read-only ですが、expert page の読み込みや OS file cache の利用によりストレージ I/O と page-cache/RAM 使用が発生し得ます。特に利用可能 RAM が不足するとファイル側からの供給が遅くなる場合があると usage に記載されています。性能値は測定条件依存のため、ここでは一般的な速度向上を断定しません（`src/program/generate.cpp:1060-1063,5710-5715`）。

## 根拠

- parser state の初期値と flag 定義: `src/program/generate.cpp:536,2753-2755`
- usage の説明と位置引数: `src/program/generate.cpp:808-810,1060-1063`
- file source 選択、open、出力、失敗時 return: `src/program/generate.cpp:5707-5724`
- mmap source の pack 検査と `experts.bin` mapping: `src/core/expert_source.cpp:1351-1433,1452-1519`
- native GGUF shards の mapping と範囲検証: `src/core/expert_source.cpp:1652-1732`
- resident/file から expert を選ぶ実使用箇所: `src/core/expert_source.cpp:4561-4598`
- 関連 option の条件と conflict: `src/program/generate.cpp:2757-2776,3040-3047`
