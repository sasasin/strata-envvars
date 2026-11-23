# `--conversation-spill-persist`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--conversation-spill-persist` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--serve` の会話再利用で使う SSD spill tier の保存先を、プロセス終了後も残す。指定すると、再起動後に同じモデル・設定の spill entry を読み戻せる。

## 使い方

```sh
strata-hy4-metal --model /data/strata/models/model.strata --serve --session-reuse 1 --conversation-spill-persist
```

この例では、モデルのパスに `/models/` が含まれるため、既定の spill root は `/data/strata/conversation-spill` になる。パスの規則は `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78` を参照。

## 値と既定値

値は不要で、指定すると真になるフラグ。省略時は `false`。parser は同じ指定を複数回受けても真のままで、値の検証は行わない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1497,1599`）。

## 実行時の動作

parser の値は `--serve` の `ServeOpts` に渡される（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1654`）。spill は、さらに `--session-reuse 1`、空でない spill root、正の `--conversation-spill-mib` がそろった場合だけ初期化される（`engine/src/hy4flash/metal/hy4_metal_serve.h:273-276`）。

spill root は `--conversation-spill-dir` があればその値、なければ session reuse が有効でモデルパスに `/models/` が含まれる場合の `<data>/conversation-spill`。それ以外は空で spill は無効になる（`engine/src/hy4flash/metal/hy4_metal_spill.h:71-78`）。

永続モードの保存先は `<spill root>/hy4-<fingerprint>`。fingerprint はモデル名・ファイルサイズと更新時刻、Engram の同情報、context、ring、sparse slot 数、layer 数、spill format version から作られる（`engine/src/hy4flash/metal/hy4_metal_spill.h:41-63,181-199`）。起動時にこのフォルダーの有効な entry を採用し、spill tier から要求の token prefix に合う会話を再利用する（`engine/src/hy4flash/metal/hy4_metal_spill.h:476-502`; `engine/src/hy4flash/metal/hy4_metal_serve.h:383-390,439-459`）。

終了時は writer を drain した後、`--conversation-min-tokens` 以上の resident conversation のうち、spill にまだ保存されていないものを書き込む（`engine/src/hy4flash/metal/hy4_metal_serve.h:570-592`）。上限は [同コマンドの `--conversation-spill-mib`](--conversation-spill-mib.md) で決まり、上限超過時は古い entry を削除する。長くなった会話が既存 entry の token prefix なら、その短い entry も置き換わる（`engine/src/hy4flash/metal/hy4_metal_spill.h:431-453`）。

## 適用条件と副作用

- 効果があるのは `--serve` の実行経路だけ。モデルの読み込み後、`--load-only` が指定されていれば serve 処理に入る前に終了する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1637`）。それ以外の通常実行では parser がフラグを受理しても `ServeOpts` に渡されない。
- `--session-reuse 1` が必要。spill root は [`--conversation-spill-dir`](--conversation-spill-dir.md) で指定でき、既定ではモデルパスに `/models/` を含める必要がある。spill の容量が 0 以下でも tier は起動しない。
- 保存先には会話 token と Metal runner の KV spill data がファイルとして書かれる。永続モードでは shutdown 時もフォルダーを削除せず、次回起動で再利用する。永続モードを無効にした通常の spill は `.p<PID>` の一時フォルダーを使い、shutdown 時に削除する（`engine/src/hy4flash/metal/hy4_metal_spill.h:191-200,325-335`）。
- `--conversation-min-tokens` 未満の会話は終了時の保存対象にならない（`engine/src/hy4flash/metal/hy4_metal_serve.h:576-578`）。

## 出力とエラー

spill が初期化されると `INFO` 行の `persist=1` で状態を出力し、採用した entry 数を stderr に `[spill] adopted ... conversations` と出す（`engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`; `engine/src/hy4flash/metal/hy4_metal_spill.h:499-502`）。spill directory を作成できない場合は stderr に `[spill] cannot create ...: spill off` を出し、その tier を無効にする（同 `hy4_metal_spill.h:188-200`）。entry の書き込みに失敗した場合は一時ファイルを削除して失敗を返し、CLI の終了エラーにはせず、spill entry を登録しない（同 `hy4_metal_spill.h:386-428`）。

## 根拠

- parser と既定値: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497,1592-1599`
- serve 経路への転送と spill 初期化条件: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1654`; `engine/src/hy4flash/metal/hy4_metal_serve.h:273-276`
- spill root と fingerprint: `engine/src/hy4flash/metal/hy4_metal_spill.h:41-78`
- 永続 directory、startup adoption、shutdown: `engine/src/hy4flash/metal/hy4_metal_spill.h:181-200,325-335,476-502`
- 終了時の resident conversation 保存: `engine/src/hy4flash/metal/hy4_metal_serve.h:570-592`
- 索引上の scope: `docs/cli/README.md:1358-1372`
