# `--context`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` などの source setup 入口 |
| オプション | `--context` |
| 別名 | なし |
| 値 | 整数（`argparse` の `type=int`）。parser に正数・上限の指定なし |

## 役割

モデルを新規導入または `--setup` で再設定するとき、会話で一度に扱うトークン数（context length）を指定します。選んだ値はモデル family ごとの設定経路を通り、主にエンジン引数 `--max-context` に反映されます。未指定時は対話選択または family / ハードウェアに応じた既定値が使われます。

## 使い方

```sh
# Linux: Qwen3.8-Flash-Next Q2_0 を 65,536 tokens でセットアップし、モデル起動はしない
./setup.sh --setup --family qwen --model Q2_0 --context 65536 --no-start
```

この例はモデルファイル等の取得・準備や設定ファイルの作成を行うセットアップ操作です。`--no-start` は完了後のモデル起動を抑止しますが、セットアップ自体を dry-run にはしません。

## 値と既定値

- 値は整数として解析されます。整数でない引数は `argparse` が拒否し、usage とエラーを表示して終了します（`terminal/setup.py:11444-11453, 11605-11606`）。`--context` 自体には `choices`、正数条件、上限条件がありません。
- 多くの経路で `a.context` が真の場合に明示値として採用されます。したがって `0` は未指定と同様に扱われ、対話選択または既定値に進みます。負数は真として通過するため、setup 側の共通 parser では拒否されません。値域外の数値をエンジンがどう扱うかは、この setup ソースだけでは確定できません（`terminal/setup.py:9875-9886, 10301-10320, 10777-10796, 12144-12161`）。
- Qwen3.8-Flash-Next / Swift の基本経路では未指定時に候補一覧を表示し、通常は GPU と RAM に基づく推奨値を初期選択します。`--yes` では質問を出さず、その既定選択が使われます（`terminal/setup.py:12144-12161`）。
- Qwen3.6 等の own-path family はモデル固有の候補から GPU 推奨値を選びます。Hy4-Flash は既定 128K、Inkling-2-Mini は既定 32K の候補を表示し、それぞれ推奨値が選択されます（`terminal/setup.py:9875-9886, 10301-10320, 10777-10796`）。Intel Arc の既存モデル取り込み経路では値がない場合 32768 が渡されます（`terminal/setup.py:9414-9420`）。
- Apple Silicon の通常 setup は `setup.py` から `engine/metal/setup_mac.py` に委譲します。Mac 側は未指定値を RAM に基づく推奨 context に置き換えます（`terminal/setup.py:9290-9294, 11452`; `engine/metal/setup_mac.py:372-403, 458-461`）。

## 実行時の動作

- 基本の Flash-Next / Swift 経路では、明示値を対話選択より優先します。選択結果は `resolve_rope` に渡され、最終的な context を基準に実行設定が組み立てられます（`terminal/setup.py:12144-12188`）。RAM 推定値を超える長文脈でも値は保持し、条件に応じてメモリ不足・低速化の警告を表示します。推奨値は上限ではありません（`terminal/setup.py:12162-12169`）。
- この基本経路では、訓練長 262144 を超える値に対し、`--rope-scaling` 未指定かつ対話実行なら方式を質問します。`--yes` または省略された方式は yarn になります。`--rope-scaling none` は訓練長超過時に拒否され、`--rope-scale` は有限値かつ 1 以上でなければならず、指定するなら方式は `linear` または `yarn` が必要です（`terminal/setup.py:9260-9286, 12170-12187`）。これらの失敗は setup のエラー表示と終了コード 1 につながります（`terminal/setup.py:1049-1056, 12180-12183`）。
- 通常経路は設定の engine args に `--max-context <値>` を加えます。context が 8192 を超える場合などは KV cache の選択も行われるため、context は必要メモリと KV の既定選択にも関係します（`terminal/strata_control/setup_config.py:218-225, 376-409`; `terminal/setup.py:12189-12205`）。
- 低 VRAM の単一 GPU で Unsloth を使う場合、見積もり上そのままでは開始できない構成に限り、setup は自動調整案を適用することがあります。ただし明示された `--context` は固定値として planner に渡され、context を自動で下げないようにします（`terminal/strata_control/setup_config.py:376-409`）。
- own-path family では値をエンジン引数に含めます。Qwen3.6 の基本経路は 262144 超を警告するものの値を保持し、この経路には RoPE scaling がまだないと明記します（`terminal/setup.py:9875-9893, 9985`）。Hy4-Flash と Inkling-2-Mini は候補・配置計画に値を渡し、選択結果を `--max-context` として設定します（`terminal/setup.py:10301-10326, 10374; 10777-10802, 10891`）。
- Mac 経路は選択値を engine args 作成関数へ渡して設定 JSON に保存します。推奨済み測定長を超えても値は保持し、測定上限を超えた旨を表示します（`engine/metal/setup_mac.py:157-160, 458-461, 593-612`）。
- 既存モデルを `--setup` なしで通常起動する場合、`--context` は保存済み設定に適用されません。指定があればその旨を警告し、保存済み設定を維持します。変更には `--setup --model ...` が必要です（`terminal/setup.py:11734-11739`）。

## 適用条件と副作用

- 新規セットアップ、モデル指定、または `--setup` でモデルを設定する経路に適用されます。`--check`、更新、既存モデルの単純起動などでは値が設定変更に使われない場合があります。通常起動時の無視は警告されます（`terminal/setup.py:11730-11739`）。
- setup は値に応じた実行設定を生成し、設定 JSON と起動スクリプトを書きます。通常のセットアップではモデル等のファイル取得・準備も行われます（`terminal/setup.py:12521-12527`）。`--no-start` を付けない場合、完了後にモデルを起動する経路もあります。
- context が長いほど cache に必要なメモリが増えます。setup は推奨値を超える値を一律拒否せず、確認できる推定超過を警告します。実際に起動可能かはハードウェア、family、エンジンに依存します。

## 出力とエラー

- 通常経路は選択した値を `context: ... tokens` として表示します。推奨 RAM 見積もりを超えると、値を保持したまま遅延またはメモリ不足の可能性を警告します（`terminal/setup.py:12162-12169, 12188`）。
- 基本経路の `--context` そのものに対する数値範囲エラーは setup parser にはありません。整数変換エラー、RoPE の組み合わせエラー、または後続の family / engine 固有処理での失敗は別経路です。後続エンジンの context 範囲検証・起動時メッセージは本調査では追跡していません。

## 根拠

- `terminal/setup.py:11444-11453, 11605-11606` — 共通 parser の定義と引数解析。
- `terminal/setup.py:11734-11739` — 通常起動時に context 指定を警告し、保存設定を維持する分岐。
- `terminal/setup.py:12144-12188, 12189-12205` — 基本 family の既定選択、明示値、RAM 警告、RoPE、KV 選択。
- `terminal/setup.py:9260-9286` — context と RoPE の組み合わせ・factor validation。
- `terminal/strata_control/setup_config.py:218-225, 376-409` — `--max-context` 設定と低 VRAM Unsloth の自動調整条件。
- `terminal/setup.py:9875-9893, 9985; 10301-10326, 10374; 10777-10802, 10891; 9414-9420` — own-path、Hy4、Inkling、Intel Arc の別経路。
- `terminal/setup.py:9290-9294`; `engine/metal/setup_mac.py:372-403, 458-461, 593-612` — Mac への委譲、parser、既定値、設定生成。
- `terminal/setup.py:1049-1056` — setup が明示的に失敗させる場合の表示と終了コード。
