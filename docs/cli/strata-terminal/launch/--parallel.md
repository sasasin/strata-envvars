# `--parallel`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 整数 `N`（1〜64）。最大同時リクエスト数 |

## 役割

モデルへのリクエストを最大いくつ同時にデコードするかを指定する。上限を増やすと各リクエストの待ち時間を減らせる場合がある一方、各スロットが会話状態用のメモリを使う。値が大きくてもハードウェアがその数を実行できるとは限らず、実際のスロット数はエンジン側の対応範囲に従う（`terminal/strata_cli/launch/cmd.py:97`、`terminal/serve/server_parts/engines.py:803-819`）。

## 使い方

```sh
strata launch --model iq3_xxs --parallel 2 --no-tui
```

`--model` などで起動対象を選び、`--parallel N` で同時リクエスト数を指定する。`--no-tui` は画面を開かずに起動する指定（`terminal/strata_cli/launch/cmd.py:77-80, 83, 97, 149`）。

## 値と既定値

- `N` は整数で、`1` から `64` まで。別の文字列は「リクエスト数ではない」、範囲外は「エンジンが実行できる範囲外」として parser が拒否する（`terminal/strata_cli/launch/cmd.py:63-70`）。引数を省略した場合、通常は利用可能な GPU メモリに応じて自動選択する。基準はおおむね 32 GB 以上で 4、24 GB 以上で 3、20 GB 以上で 2、それ未満で 1（しきい値判定には 0.5 GB の許容幅がある）。Qwen3.6 の独自エンジン経路ではモデルと context を使う setup 側の推奨数を参照し、この表の値を上限にする（`terminal/strata_cli/launch/settings.py:58-68`、`terminal/strata_cli/launch/runner.py:444-458`）。
- `--preset NAME` を指定した場合は保存済み設定を読み込み、明示した `--parallel` があればその値で上書きする。プリセットに値があり、CLI で省略した場合はその設定を保持する（`terminal/strata_cli/launch/cmd.py:215-221, 252-253`）。プリセットなしの場合は自動選択（`terminal/strata_cli/launch/settings.py:103-118`）。
- 値を複数回指定した場合の個別処理は確認できなかった。parser は同じ引数を複数回指定した場合の独自 validation を定義していない（`terminal/strata_cli/launch/cmd.py:97`）。

## 実行時の動作

明示値は launch 設定に格納され、起動用 profile の `parallel` 上書き値になります。省略時は選択済みモデル・GPUから値を決め、profile に保存します。`strata launch` の profile override には host、port、parallel が入り、毎回その launch の選択値で上書きされます（`terminal/strata_cli/launch/cmd.py:215-253`、`terminal/strata_cli/launch/runner.py:2247-2270, 2289-2294`）。

サーバーはこの値を通常のエンジンでは `--batch N` に変換し、最大 N 件を同時にデコードさせ、残りを待たせます。全 GPU split engine では既存の `--batch` を lane 数として更新し、最大 8 に制限します。Inkling-2-Mini のネイティブエンジンでは `--parallel N` を渡し、最大 64 に制限します（`terminal/serve/server_parts/engines.py:816-851`）。

省略時の自動値には例外があります。Hy4-Flash はエンジンに複数 slot がなく、常に 1 件ずつです。DFlash2 が選ばれた場合、利用者が数を明示しなければ 1 件ずつにする分岐があります。明示値がある場合はその分岐を適用せず、slot 数と drafter の組み合わせをサーバー側の drafting 処理で決めます（`terminal/strata_cli/launch/runner.py:1140-1148, 2028-2035, 2247-2257`、`terminal/serve/server.py:3552-3563`）。

## 適用条件と副作用

- 一般のエンジンは layer split なしで最大 8 slot。split 時は split engine が最大 8 lane を扱います。Inkling-2-Mini はネイティブの連続 batching で 1〜64 を受け付けます。したがって CLI の上限 64 は全モデル共通の実行保証ではありません（`terminal/serve/server_parts/engines.py:803-807, 826-851`）。
- 一般エンジンで 8 を超える値は、`--batch-mtp` が有効でなく layer split でもない場合、エンジンが標準出力に上限 8 で動作する旨を表示し、`--batch` を渡します。split ではこの警告・上限分岐が異なり、実行 slot 数はエンジンが通知します（`terminal/serve/server_parts/engines.py:845-851`）。
- GPU メモリが足りない場合、Strata は context や要求 slot 数を勝手に下げず、KV 等を GPU 外へ移す調整を試みます。起動時にも収まらなければエンジン起動が失敗し、ログから「同時リクエスト数を減らす」案内が表示されます（`terminal/serve/server.py:3579-3594`、`terminal/strata_cli/launch/runner.py:3221-3238`）。
- インストール設定のエンジン引数に `--batch` または `--slots` がすでに含まれる場合、通常エンジン向けの変換処理は追加の batch 指定を行いません。server の直接起動 parser に `--parallel` を渡す経路では、この組み合わせは競合として拒否されます。all-cards split engine は例外として既存の `--batch` を lane 数に使います（`terminal/serve/server_parts/engines.py:809-835`）。

## 出力とエラー

`N` が整数でない場合、または `1..64` の範囲外の場合、argparse の型エラーとして値の範囲を案内します（`terminal/strata_cli/launch/cmd.py:63-70, 97`）。起動時に GPU メモリに収まらない場合は起動失敗となることがあり、Terminal は engine log の失敗理由を表示して、同時リクエスト数を 1 減らす案内を出します（`terminal/strata_cli/launch/runner.py:3221-3238`）。通常エンジンで 8 を超える値を使う場合の上限案内は engine の標準出力に出ます（`terminal/serve/server_parts/engines.py:847-851`）。

## 根拠

- parser、型変換・範囲 validation: `terminal/strata_cli/launch/cmd.py:63-70, 97`。
- 初期値と GPU メモリ別の自動選択: `terminal/strata_cli/launch/settings.py:58-68, 103-118`。
- プリセットへの適用: `terminal/strata_cli/launch/cmd.py:215-221, 252-253`。
- model/context と GPU の自動値、例外時の動作: `terminal/strata_cli/launch/runner.py:444-458, 1140-1148, 2028-2035, 2247-2294`。
- profile override の保存: `terminal/strata_cli/launch/runner.py:2247-2270`。
- 同時 slot をエンジン引数に反映する処理・上限: `terminal/serve/server_parts/engines.py:803-851`。
- drafting、メモリ調整・起動時の適用: `terminal/serve/server.py:3552-3594`。
- メモリ不足時の案内: `terminal/strata_cli/launch/runner.py:3221-3238`。

