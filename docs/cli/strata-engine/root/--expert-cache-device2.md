# `--expert-cache-device2`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンのトップレベル引数） |
| オプション | `--expert-cache-device2` |
| 別名 | なし |
| 値 | `N`（CUDA2 に置く expert 数）または `auto` |

## 役割

CUDA2 に追加の expert cache を作り、CUDA0 の通常キャッシュに入らなかった expert の一部を CUDA2 上で計算します。CUDA2 は CUDA1 に続く2枚目の helper GPU です。CUDA0 は dense 層・状態などと通常の expert cache を担当し、helper が計算した行は pinned host memory 経由で戻ります。GPU 数を増やしても自動で有効にはならず、このオプションと CUDA1 用の設定が必要です。

## 使い方

モデル pack のある環境で、例として CUDA1 に 2,048 slots、CUDA2 に空き容量に合わせた cache を設定します。

```text
strata --pack ./model --expert-profile ./profile.bin --expert-cache 4096 --expert-cache-device1 2048 --expert-cache-device2 auto
```

`--expert-cache-device2` を正数にする場合は `--expert-cache-device1` も正数にしてください。リモート cache 全体には CUDA0 の `--expert-cache`、非空の `--expert-profile`、expert pool が必要です。

## 値と既定値

- 省略時の内部値は `0` で、CUDA2 helper cache は無効です。別名はありません。
- 数値 `N` は `std::atoi` で整数に変換され、その数が CUDA2 cache の slot 上限になります。正数で有効、`0` は無効、負数は後段の resource validation で拒否されます。
- `auto` は slot 上限を `INT_MAX` として扱い、`auto` 指定フラグも立てます。実際には CUDA2 の空き VRAM と expert blob のサイズを見ながら選び、cache として確保する分の後にも 512 MiB を残せるところまで格納します。
- 引数値が欠けると parser は `--expert-cache-device2 needs a value` を stderr に出して終了コード 2 で終了します。数値以外の文字列（`auto` 以外を含む）は `atoi` の結果 0 になるため、明示的な形式エラーにはならず、CUDA2 cache を無効にします。重複指定は parser が順に代入するため、後の値が残ります。

## 実行時の動作

parser は `--expert-cache-device1..3` を共通処理し、末尾の数字から内部配列の index を決めます。したがって本オプションは配列 index 1（CUDA2）に対応します。CUDA2 の値が正数なら CUDA1 の値も正数でなければならず、違反時は `invalid sampling or resource parameter` を stderr に出し終了コード 2 となります。

helper cache の初期化は CUDA1 が有効なときに行われ、CUDA0 cache と expert profile にある順位を基に、CUDA0 cache や layer split の cache が保持していない expert を選びます。CUDA2 または CUDA3 も有効なら複数 GPU 配置になり、既定の配置 `stripe` では候補を CUDA1/2/3 の有効な cache に順に割り当てます。`--expert-cache-remote-placement layer` を併用すると layer 番号を helper 数で割った担当 GPU に配置します。この設定自体は配置方式を変える別オプションで、既定値は `stripe` です。

複数 GPU の配置時、またはいずれかの helper に `auto` を指定した場合、profile の順位リストは未掲載の `(layer, expert)` にも拡張されます。未掲載分は expert 番号、次に layer 番号の順で追加されます。`auto` は候補を CUDA2 に無制限に割り当てる指定ではなく、実バイト数を使って空き VRAM と 512 MiB の余白を保ちながら選定します。数値指定は slot 数で制限します。

## 適用条件と副作用

- CUDA2 が見えており、CUDA0（primary）とは異なるデバイスである必要があります。通常は可視 GPU ordinal 2 が CUDA2 です。`STRATA_PRIMARY_DEVICE` による primary の変更時や layer split 時は、helper の割当て先が通常時と異なります。
- layer split と併用する場合、helper は split のどの stage も実行しない可視 GPU に割り当てられます。その GPU が足りなければ起動時に拒否されます。
- 数値指定でも自動縮小はされません。cache の確保後に 512 MiB を残せない場合は失敗します。`auto` は helper ごとに空き容量を見て候補を止めますが、1件も収まらない場合は失敗します。
- helper cache の有効化には GPU context、expert cache、GPU stream/buffer および pinned host staging memory が追加され、モデル expert の読み込みと CUDA2 での計算が発生します。各 layer の helper 計算結果は pinned host rows 経由で戻り、layer の継続は参加 helper の処理を待ちます。P2P 転送を行う設定ではありません。
- `--peer-device` は `--layer-split` または helper cache と併用できません。CUDA1/2 の helper を使うには CUDA0 の `--expert-cache`、profile、expert pool が必須です。
- `--remote-expert-opt` は `--serve` と CUDA1 helper cache を必要とします。これは別の任意最適化であり、本オプションだけでは有効になりません。

## 出力とエラー

初期化成功時は stderr に CUDA device ごとの resident expert 数と GiB 数を表示します。serve mode の各 request では CUDA2 の computed expert entries、active layer launches、転送 MiB、staging/launch と待ち時間を表示します。非 serve 経路でも実行終了時に CUDA2 で計算した routed entries 数を表示します。

CUDA2 が可視でない、primary と同一、空き容量が不足、候補 expert がない、cache fill に失敗した場合などはエラーを stderr に出します。CUDA2 cache の初期化失敗は終了コード 1 です。一般的な負数や CUDA1 未設定などの resource validation、layer split 用 GPU 不足は終了コード 2 です。

## 根拠

- 索引上の配置と scope: `docs/cli/README.md:1128-1135,1171-1177`（`strata-engine` の `strata` root parser 配下）。
- engine help 表示: `src/program/generate.cpp:999-1011`（値形式、CUDA2 の説明、関連 peer cache の注意）。
- parser、引数不足、内部値: `src/program/generate.cpp:2416-2420,2562-2567`。既定値の 0 は同ファイル `src/program/generate.cpp:559-562`。
- 連続する helper tiers と layer split 時の device 決定: `src/program/generate.cpp:3048-3067,3130-3141`。
- resource validation と peer/device 併用制約: `src/program/generate.cpp:3352-3375`。
- helper cache が要求する CUDA0 cache/profile/pool、および複数 GPU の順位拡張と配置: `src/program/generate.cpp:6662-6729`。
- helper cache の初期化、エラー伝播、起動ログ: `src/program/generate.cpp:6731-6746`。
- 自動容量計算、512 MiB の確保余地、cache fill: `src/core/remote_experts.cpp:135-195`。device 可視性と primary device の事前検査: `src/core/remote_experts.cpp:70-96`。
- serve request ログ: `src/program/generate.cpp:15666-15675`。非 serve 終了時の集計: `src/program/generate.cpp:16962-16964`。

本調査は指定 revision のソースを対象とし、同 revision のビルド済み engine/help や Release 配布物は確認していません。Qwen3.5 など family 固有 parser に引数が転送された後の受理可否、実 GPU ごとの容量・互換性はこの文書では検証していません。
