# `--expert-cache`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン。Terminal CLI の `strata` とは別プログラム） |
| オプション | `--expert-cache N` |
| 別名 | なし |
| 値 | `auto` または整数。整数 `N` は expert cache のサイズ予算に使う |

## 役割

GPU VRAM に expert blob を常駐させ、cache に載った expert の計算を GPU 上で行います。cache にない expert は通常の CPU expert pool 側で処理されます。Mixture-of-Experts モデルの GPU expert cache を調整するためのオプションです。

`N` は厳密な「実際に確保する expert slot 数」ではありません。通常は最大サイズの expert blob を単位とするサイズ予算として使われ、モデル、expert profile、VRAM の空き、関連オプションにより、最終的な slot 数が変わります。

## 使い方

```sh
strata --serve --pack /path/to/model.pack \
  --expert-profile /path/to/expert-profile.bin \
  --expert-cache auto
```

固定予算を指定する例:

```sh
strata --serve --pack /path/to/model.pack \
  --expert-profile /path/to/expert-profile.bin \
  --expert-cache 7000
```

実際の推論ではモデル形式に応じて `--pack` やモデル入力など、エンジンが必要とする他の引数も指定します。Strata Terminal を通して起動する場合、Terminal が保持する run config の `args` にエンジン引数が設定されます。Terminal CLI の `strata launch` にこのエンジン引数をそのまま渡す形式とは限りません。

## 値と既定値

| 指定 | 実装上の扱い |
| --- | --- |
| 省略 | 初期値は `0`。expert profile を読み込まない経路では cache を作らない。expert profile を読み込むと `0` は自動サイズ指定として扱われる |
| `auto` | `-1` に変換され、自動サイズ指定になる |
| `0`（profile なし） | cache 無効 |
| `0`（profile あり） | profile の読み込み後に `auto` 相当へ変換される |
| 正の整数 `N` | 固定サイズ予算として処理する。VRAM や profile 等の上限により、最終 slot 数は要求より小さくなる場合がある |
| `-1` | `auto` と同じ内部値 |
| `-2` 以下 | 無効な resource parameter として終了コード `2` で拒否される |
| 数値で始まらない文字列 | `std::atoi` が `0` を返すため、`0` と同様に扱われる。profile の有無で結果が変わる |

数値は `std::atoi` で変換されます。そのため、`7000xyz` のような値も先頭の数値部分が変換され、厳密な整数文字列検証はされません。値が必要なのに後続引数がない場合は `--expert-cache needs a value` を出して終了コード `2` になります。

`--expert-cache=7000` の等号形式は parser に定義されていません。オプション名と値を別々の引数にして `--expert-cache 7000` と指定してください。同じオプションを複数回書いた場合は引数走査中に値が上書きされ、最後に指定した値が残ります。

## 実行時の動作

1. parser は次の引数を値として読み、`auto` なら内部値 `-1`、それ以外は `std::atoi` の結果を保存します。
2. 値が `-1` より小さい場合は、一般的な `invalid sampling or resource parameter` エラーで終了します。
3. expert profile を指定して正常に読み込んだ場合、内部値が `0` なら `-1`（自動）に変更します。profile がない場合の初期値 `0` は cache を有効化しません。
4. 自動指定では、モデルの重み・session・draft head などの割り当て後に取得した GPU 空きメモリから cache を見積もります。予約メモリなどを差し引き、モデル形式や実行 backend に固有の調整も行います。実際の cache 確保後にも空き VRAM を確認し、reserve を満たせない場合は自動 cache を縮小して再試行します。
5. 正の固定値では、その値と expert blob のサイズを基に予算を計算します。native pack では blob のサイズ差を考慮し、profile の順序に沿って予算に収まる expert を選びます。profile が要求数より短い場合は profile が上限になり、警告を出すことがあります。
6. 有効な profile があれば、profile の順位に従って cache を事前に埋めます。profile がない場合は起動時に `compulsory-miss` policy と表示され、実行中に要求された expert で埋まります。

## 適用条件と相互作用

- この option が制御するのは GPU expert cache です。cache に載った expert は GPU で計算されるため、CPU で計算する場合と浮動小数点の丸め順序が異なり、出力がわずかに異なることがあります。これはソース内で案内されている注意点で、どちらがより正しいかを意味するものではありません。
- `--expert-profile` が指定されると、profile に含まれる expert の順位が cache の事前充填に使われます。profile を使わない場合は、profile 順の事前充填ではなく compulsory-miss の方式になります。
- `--expert-cache-per-layer` が有効な native pack では、同じ予算から各 layer に同数ずつ slot を確保する形式になります。通常の `--expert-cache N` は最大 blob サイズを基準とする予算のままです。
- `--vram-reserve-mib` は cache 確保後に残す VRAM 量に関係します。multi-GPU layer split では、明示値が prompt buffer と reserve の場所を圧迫する場合、警告して cache slot 数を縮めます。
- `auto` では確保後の空き VRAM を見て縮小する処理があります。固定値ではこの auto-only の再確認・縮小を行わず、WDDM では過大な確保が system memory への paging を招き、起動が成功しても推論が大幅に遅くなることがあります。起動後の `LOW` VRAM 表示にも注意してください。
- cache が `0` のときや `--no-pool` 指定時には GPU expert cache hit path の計算バッファを構成しません。
- Intel SYCL にも同じ option parser を持つ実装がありますが、backend ごとの cache allocator・メモリ制約には差があります。上記の VRAM 再確認・WDDM 説明はソースで確認した CUDA/HIP 系の実装と資料に基づき、全 backend 共通の保証としては扱いません。

## 利用上の目安

- 自動調整を使いたい場合は `--expert-cache auto` を指定します。profile がある構成では setup が通常 `--expert-cache auto` を生成します。
- 明示的な数値を使う場合、`N` を GiB や byte 数として解釈しないでください。現行の説明上は「最大サイズ expert blob を単位にした概算予算」です。実際に確保された slot 数や VRAM は起動ログで確認します。
- 固定値を増やすと cache に入る expert が増える可能性がありますが、VRAM の残量も減ります。特に Windows WDDM では起動後の空き VRAM が極端に少ない設定で paging が起こり、速度低下につながることがあります。必要な VRAM reserve を残すか、`auto` を利用してください。
- 性能効果はモデル、profile、GPU、VRAM、context、他の割り当てで変わるため、このオプションだけから速度向上を保証できません。`docs/DETAILS.md` の測定例では RTX 4080 SUPER 32 GB、IQ3_S、engine 0.1.39 で、固定 8900 slots の設定は VRAM 残量が 0 MiB となり低速化し、`auto` や小さな固定値ではより多くの空きを残した例が記載されています。これはその測定条件での結果であり、他機材への一般化はできません。

## 根拠

- `src/program/generate.cpp:999-1002` — help 表示。初期既定値 `0` と cache の役割を記載。
- `src/program/generate.cpp:558` — `Options::expert_cache` の初期値。
- `src/program/generate.cpp:2413-2421,2557-2561` — 引数走査、値欠落時の処理、`auto` と `std::atoi` による変換。
- `src/program/generate.cpp:3352-3359` — `-1` 未満の拒否とエラー終了コード。
- `src/program/generate.cpp:4414-4424` — expert profile 読み込み、および profile がある場合の `0` を auto とする処理。
- `src/program/generate.cpp:6013-6020,6041-6064,6114-6133` — cache サイズ算定のタイミング、自動 sizing、統合 GPU のメモリ調整、Mac の auto 上限。
- `src/program/generate.cpp:6182-6202,6213-6219,6222-6280` — 最低 slot が足りない場合の診断、layer split の縮小、native pack と profile による実 slot 数の算定。
- `src/program/generate.cpp:6367-6413` — 確保失敗時の auto 縮小再試行と Windows page file の案内。
- `src/program/generate.cpp:6420-6439,6441-6453` — cache の丸め差に関する表示、profile/compulsory-miss policy と事前充填。
- `src/program/generate.cpp:6838-6850` — cache hit path 用 GPU buffer の確保条件。
- `src/program/generate.cpp:11020-11030` — server 起動時の低空き VRAM 表示と、auto 固定値の扱いの違い。
- `setup.py:9418-9421` — setup が生成する run config に `--expert-profile` と `--expert-cache auto` を含める例。
- `docs/DETAILS.md:756-780` — 固定予算と auto の再確認の違い、および RTX 4080 SUPER での測定例。

