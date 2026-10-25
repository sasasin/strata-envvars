# `--rope-scaling`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--rope-scaling` |
| 別名 | なし |
| 値 | `none`、`linear`、`yarn` のいずれか。値を取る。 |

## 役割

実行全体で使う RoPE（回転位置埋め込み）のスケーリング方式を選びます。`linear` は位置角を一様に縮小し、`yarn` は周波数帯ごとに補間と外挿を組み合わせます。`none` はスケーリングを無効にします。これはコンテキスト長の設定そのものではなく、長いコンテキストで使う RoPE の方式を指定するものです（`src/program/generate.cpp:450-463, 806-875`、`include/strata/kernels/rope_scaling.hpp:3-12`）。

## 使い方

```sh
strata generate --pack DIR --native SHARD1 --spec 2 --prefill 8192 \
  --tokens "1,2,3" --max-context 524288 --rope-scaling yarn --rope-scale 2
```

これはエンジンの引数形式を示す例です。`DIR`、`SHARD1`、トークン列は実際のモデルと入力に合わせてください。`--rope-scale` はスケーリング係数を設定する別オプションで、`--rope-scaling` 単独では係数を指定しません（usage: `src/program/generate.cpp:806-812, 856-875`）。

## 値と既定値

- 値は小文字で厳密に `none`、`linear`、`yarn` のいずれかです。parser は文字列を保存し、起動時に許可値を検査します。別の値は stderr に許可値を表示して終了コード `2` で終了します（`src/program/generate.cpp:2444-2454, 3312-3327`）。
- オプション省略時は内部値が空文字列のままで、エンジンの設定既定値 `none` を使います。`--native` で読み込む GGUF に `rope.scaling.type` があれば、その値が省略時の方式になります。明示した `--rope-scaling` は GGUF より優先されます（`src/program/generate.cpp:450-455, 3642-3647, 3681-3694`）。
- 値を省略すると `--rope-scaling needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2421`）。同じ引数を複数回指定した場合は parser の逐次代入により最後の値が残ります（`src/program/generate.cpp:2416-2421, 2446`）。
- `--rope-scale` など数値ノブはこの方式と組み合わせて設定します。`--rope-scale` を省略または `0` にすると、GGUF の係数があればそれを使い、なければ係数 `1` です。明示値 `1` も GGUF より優先されます（`src/program/generate.cpp:456, 3645-3647, 3696-3697`）。

## 実行時の動作

エンジンは起動時に CLI 値と（`--native` の場合）モデル GGUF の RoPE metadata を解決し、セッション初期化より前にプロセス共通設定を一度だけ登録します。KV キャッシュには RoPE 適用後のキーが格納されるため、設定は実行中・リクエストごとには変更できません（`src/program/generate.cpp:450-454, 3642-3647, 3653-3674, 3681-3731`、`include/strata/kernels/rope_scaling.hpp:30-35, 186-191`）。

- `none` は GGUF のスケーリング方式を明示的に無効化します。スケーリング用ノブは効果を持たず、`--rope-scale` が `1` より大きい、`--rope-freq-scale` が正、または一部の YaRN ノブが明示されている場合は無効である旨を stderr に通知します。周波数 base は回転自体に使うため保持されます（`src/program/generate.cpp:3681-3686, 3708-3719`）。
- `linear` と `yarn` では、角度縮小率は `--rope-freq-scale` が正ならその値、そうでなければ `1 / factor` です。factor は `--rope-scale`、GGUF metadata、既定値 `1` の順に決まります（`src/program/generate.cpp:3696-3707`、`include/strata/kernels/rope_scaling.hpp:77-90`）。
- `yarn` の補正に関係する元コンテキスト、補正係数、attention 係数、beta 値は `--yarn-orig-ctx`、`--yarn-ext-factor`、`--yarn-attn-factor`、`--yarn-beta-fast`、`--yarn-beta-slow` で調整できます。エンジン構造体の初期値は順に `262144`、自動値（YaRN なら `1`、それ以外なら `0`）、`1`、`32`、`1` です（`src/program/generate.cpp:459-463, 3698-3707`、`include/strata/kernels/rope_scaling.hpp:66-75`）。
- 選択した設定は通常の RoPE table の cos/sin 値に埋め込まれ、解析的な回転経路では kernel 引数として使われます（`src/core/layer.cpp:938-950`、`include/strata/kernels/rope_scaling.hpp:22-28, 102-117`）。

## 適用条件と副作用

- 適用範囲は `strata-engine` の `strata generate` です。同じ `--rope-scaling` は `setup.py` にもありますが、それは `source-setup/root` の別 CLI スコープであり、値の自動選択など設定側の挙動をこの文書の対象には含めません（エンジン parser: `src/program/generate.cpp:2444-2454`、setup parser: `setup.py:8429-8435`）。
- モデル GGUF の RoPE キーを読むのは `--native` のモデル shard がある経路です。GGUF の `rope.scaling.type` は `none`、`linear`、`yarn` のみ受理され、別の値ならエラー終了します（`src/program/generate.cpp:3653-3678, 3687-3694`）。
- 選んだ方式は `--max-context` がモデルの元コンテキスト以下でも適用されます。その場合エンジンは「拡張位置が不要でもスケーリング設定は全角度に適用される」と stderr に注記します（`src/program/generate.cpp:3732-3743`）。
- 設定はキャッシュ内の回転済みキーと session 初期化時の table/kernel に関わるため、同一実行中に変更できません。ここではユーザーが指定するファイル出力やネットワーク操作は確認できません（`include/strata/kernels/rope_scaling.hpp:30-35, 186-191`）。

## 出力とエラー

- 起動時に不正値を検出すると stderr に理由を出し、終了コード `2` で終了します。方式名の検査に加え、すべての RoPE 数値ノブの有限性、factor が `1` 以上であること、frequency base が `1` より大きいことなどの範囲を検査します（`src/program/generate.cpp:3312-3350`）。
- 解決済み設定全体も `rope_scaling_invalid` で検証され、無効なら stderr に設定値を含む診断を出して終了コード `2` になります（`src/program/generate.cpp:3721-3729`、`include/strata/kernels/rope_scaling.hpp:164-183`）。
- `linear` または `yarn` が有効な場合、方式、係数、角度縮小率、base、`--max-context` と訓練コンテキストを stderr に記録します。明示的にスケーリングが有効な一方で factor が `1` なら拡張はなくても角度への適用は残ります（`src/program/generate.cpp:3731-3743`）。

## 根拠

- parser と値取得: `src/program/generate.cpp:2416-2421, 2444-2454`
- usage 表示: `src/program/generate.cpp:806-812, 865-875`
- CLI 値の初期値・数値ノブ: `src/program/generate.cpp:450-463`
- 早期 validation: `src/program/generate.cpp:3312-3350`
- GGUF/CLI の優先順位と解決、適用ログ: `src/program/generate.cpp:3642-3743`
- table/kernel への反映と固定条件: `src/core/layer.cpp:938-950`、`include/strata/kernels/rope_scaling.hpp:22-35, 66-117, 164-191`
- 別スコープの setup parser: `setup.py:8429-8435`

調査は指定 commit のソースと作業ツリー内資料に限定しました。CLI バイナリの `--help`、Release 配布物、各 backend の実機動作は確認していません。
