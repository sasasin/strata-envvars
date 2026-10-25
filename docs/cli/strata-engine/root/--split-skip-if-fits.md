# `--split-skip-if-fits`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--split-skip-if-fits` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は無効。 |

## 役割

`--layer-split auto` で複数 GPU の層分割が有効になったとき、CUDA0 だけで expert profile の全 expert pair と全層分の session（KV）、drafter/head、verify window、VRAM reserve を収容できると判定すれば、分割を取り消して CUDA0 のみで実行します。収まらない場合や判定に必要な条件が揃わない場合は、分割を維持します。

## 使い方

```sh
strata --model MODEL.gguf --serve --layer-split auto \
  --expert-profile PROFILE.bin --split-skip-if-fits
```

`MODEL.gguf` と `PROFILE.bin` は実際に使用するモデルと対応する expert profile に置き換えます。`--serve` は `--layer-split` の必須条件です。コマンド例はオプションの構文例であり、特定のモデルや profile の適合性を保証しません。

## 値と既定値

値は不要です。parser は指定時に内部フラグを `true` にし、未指定時は `false` のままです。同じフラグを複数回指定しても真偽値を再設定するだけです。数値などを後続に渡す形式ではありません（`src/program/generate.cpp:716-719, 2633-2637`）。

## 実行時の動作

- エンジンは `--layer-split` が `auto` で、複数 GPU 分割が成立し、このフラグが指定された場合にだけ判定します。明示的な層境界指定ではこの判定に入りません。`--layer-split auto` は `--serve` がなければ拒否され、可視 GPU が1台なら自動分割を解除して「no split」として続行するため、このフラグによる fit 判定は行われません（`src/program/generate.cpp:2981-3030`）。
- 判定には `--expert-profile` の全 ranked pair を読み、各 pair の blob サイズ（native pack では slot stride）を合算します。CUDA0 の現在の空き VRAM `fb` から、全層 session の `session_bytes(...)`、`--vram-reserve-mib`、および固定 1000 MiB（drafter/head）と 96 MiB（verify windows）を差し引きます。pair 合計が残り容量以下なら分割設定をクリアし、以降は単一 GPU 経路になります。比較は `pairs_bytes <= room` なので、等しい場合も単一 GPU に切り替わります（`src/program/generate.cpp:4190-4234`）。
- 後段 stage の GPU 選択は `--split-device` の指定、または指定がなければ可視 GPU の並びに基づきますが、この判定が成功すると後段 GPU 群・split point・`--layer-split` の値を消去します（`src/program/generate.cpp:2970-3003, 4216-4227`）。
- `serve/server.py` は設定に layer split があり、設定値 `split_skip_if_fits` が真で、engine 引数にまだ同フラグがない場合にこのフラグを追加します。CLI の直接指定ではこの Python 設定処理を経由しません（`serve/server.py:3115-3119`）。

## 適用条件と副作用

- 判定は後続 stage の読み込み前に行われます。判定成功時は stage 間の hand-off を行わない単一 GPU 実行へ切り替わります。判定不成功でもエラー終了にはせず、複数 GPU split をそのまま続けます（`src/program/generate.cpp:4190-4234`）。
- リモート expert cache（`--expert-cache-device1..3` のいずれかが正数）を使う場合、または `--expert-profile` が指定されていない場合は fit 判定をせず、stderr に理由と `the split stays` を出します。profile がないこと自体はこの分岐では失敗ではありません（`src/program/generate.cpp:4195-4203`）。
- profile の読み込みに失敗した場合も判定分岐では split を維持して理由を stderr に出します。ただし、profile が指定されていれば後段でも読み込み、そこで失敗するとエラーを出して終了コード 1 になります。つまり、このフラグは不正な profile を無視して実行を続けさせるものではありません（`src/program/generate.cpp:4199-4203, 4414-4420`; `src/core/expert_cache.cpp:74-140`）。
- 空き VRAM の判定は実行時の `cudaMemGetInfo` 値を使い、ファイルや GPU の状態を変更する専用処理はありません。この判定箇所では `cudaMemGetInfo` / `cudaGetDeviceProperties` の戻り値を検査していないため、API 呼び出し失敗時に判定値・表示名がどうなるかはソースから確定できません（`src/program/generate.cpp:4209-4215`）。
- `STRATA_SPLIT_OWN` による独自 prefill buffer の選択は、`--split-skip-if-fits` が指定されている場合は抑止されます。分割を維持する経路にも適用されるため、このフラグを指定すると環境変数の値にかかわらずこの選択条件から外れます（`src/program/generate.cpp:3093-3098`）。

## 出力とエラー

- 全 pair が収まる場合、stderr に `layer split skipped (--split-skip-if-fits)`、CUDA0 名、pair 数、session 容量、空き容量、余裕量を出し、単一 GPU へ切り替えます（`src/program/generate.cpp:4216-4227`）。
- 収まらない場合、stderr に CUDA0 が保持可能な容量と profile の必要容量を示し、`the split stays` と出します（`src/program/generate.cpp:4228-4234`）。
- profile がない、リモート cache がある、profile を判定用に読めない場合も stderr に理由と `the split stays` を出します。指定 profile 自体に問題がある場合の後段エラーは前節のとおりです（`src/program/generate.cpp:4195-4203, 4414-4420`）。
- このフラグ単独の値検証エラー経路はありません。周辺の `--layer-split` 構文・`--serve` 条件違反は stderr に説明を出して終了コード 2 になります（`src/program/generate.cpp:2998-3027`）。未知引数も stderr に `unknown argument` と usage を出して終了コード 2 ですが、本フラグは現行 parser に登録されています（`src/program/generate.cpp:2633-2637, 2787-2792`）。

## 根拠

- parser と既定値: `src/program/generate.cpp:716-719, 2633-2637`
- layer split の有効条件・GPU 選択: `src/program/generate.cpp:2970-3037`
- fit 判定と分割解除、診断出力: `src/program/generate.cpp:4190-4237`
- 独自 prefill buffer 条件: `src/program/generate.cpp:3093-3098`
- profile の後段読込エラー: `src/program/generate.cpp:4414-4420`; profile 検証: `src/core/expert_cache.cpp:74-140`
- server 設定からのフラグ追加: `serve/server.py:3115-3119`
- 索引上の配置・scope: `docs/cli/README.md` の `strata-engine` → root

この調査では既存バイナリの `--help`、Release archive、GPU 実行を確認していません。記述は上記 checkout のソースに基づき、ビルド別・実機別の挙動差は確認範囲外です。
