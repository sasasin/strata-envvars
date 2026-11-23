# `strata components add-build --backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | backend family 名。parser は文字列を受理し、処理側で `cuda`、`hip`、`sycl`、`metal`、`cpu` と現 platform の組み合わせを検証する |

## 役割

手元でビルドした engine をローカル component として登録するとき、その build の backend family を明示します。指定すると `BUILD.json` から読み取る backend より優先され、現在の GPU 検出結果との family 照合は行いません。省略時は build metadata から family を読み取り、検出された GPU family（または CPU build）と一致するかを確認します。

## 使い方

```sh
# CUDA build として登録し、ローカル engine を選択する
strata components add-build ./build --backend cuda

# CPU build の場合
strata components add-build ./build --backend cpu
```

コマンドには engine 実行ファイルとその runtime libraries、`BUILD.json` がある build folder を渡します。成功すると build を component folder にコピーし、その engine を選択します。既にある同名 local engine の上書きはせず、先に `strata components remove` で削除する必要があります。

## 値と既定値

- `--backend` は値を1つ取りますが、argparse の `choices` はありません。既定値は `None`（未指定）です。parser 定義: `terminal/strata_cli/update_cmd.py:47-56,95-99`。
- 実処理は値を trim して小文字化し、指定値を build metadata より優先します。未指定なら `BUILD.json` の `backend`、または `cuda` / `hip` / `rocm` / `sycl` / `oneapi` / `metal` の toolchain fields から family を導きます。metadata の `amd` / `nvidia` / `intel` / `rocm` もそれぞれ `hip` / `cuda` / `sycl` / `hip` に変換されます。`terminal/strata_control/local_engine.py:77-93,127-138`。
- family として使える値は `cuda`、`hip`、`sycl`、`metal`、`cpu` です。ただし受理されるのは現 platform と対応する組み合わせだけです。対応表は `terminal/strata_control/targets.py:25-31,48-57` にあります。
- 明示値は metadata 用の alias 変換を通らず family として検証されます。そのため parser が受け取る文字列でも、`nvidia`、`amd`、`intel`、`hip-rdna2` のような別名・variant 名は有効 family として扱われません。family を指定してください。
- backend metadata がなく `--backend` も省略した場合、build は拒否されます。エラー案内は `cuda`、`hip`、`sycl`、`metal`、`cpu` の指定を示します。`terminal/strata_control/local_engine.py:136-142`。

## 実行時の動作

`--backend` がある場合、update command は要求 hardware を作るときに alias / `hip-*` variant を分解して hardware detection に渡します（`terminal/strata_cli/update_cmd.py:283-300,314-321`）。一方 add-build の本体には元の引数を渡すため、最終的な package family は local build 登録側の検証規則に従います（`terminal/strata_cli/update_cmd.py:425-434`）。

登録処理は build folder と `strata`（Windows は `strata.exe` も可）を確認し、platform 対応を検証します。`--backend` を指定した場合は `BUILD.json` の family より優先され、検出 GPU family との一致チェックは省略されます。未指定なら検出 family と build family が一致するか照合し、CPU build はこの照合を通過します。CUDA / HIP の `archs` が metadata にない場合は、それぞれ現在の card architecture の検出値で補います。`terminal/strata_control/local_engine.py:41-46,127-152`。

次に `strata --version` を最大10秒実行して version を読み取り、build 内の engine、隣接 runtime library、認識された vision helper、`BUILD.json` を `<components>/engine/<version>-<platform>-<backend>-local/` にコピーします。各ファイルの SHA-256 とサイズを記録した `manifest.json` を作り、full verification 後に staging directory を最終名へ移動します。ダウンロードは行いません。`terminal/strata_control/local_engine.py:28-32,48-74,109-116,153-178`。

登録後は `use_engine` で engine を切り替えます。これは明示的な利用者選択によるもので、local build は自動選択されません。`STRATA_REQUIRE_SIGNED_COMPONENTS` が `1` / `true` / `yes` / `on` の場合は unsigned package が拒否されます。`terminal/strata_cli/update_cmd.py:434-441`、`terminal/strata_control/engine_component.py:386-394`。

## 適用条件と副作用

- platform/backend の対応外なら登録を拒否します。未指定時に検出 family があり build がそれと異なる場合も拒否します。明示した `--backend` は検出 family との不一致確認を無効にしますが、platform 対応チェックは残ります。`terminal/strata_control/local_engine.py:139-145`。
- engine の `--version` が失敗する、10秒以内に応答しない、version 番号が出ない場合は登録しません。`terminal/strata_control/local_engine.py:48-74`。
- 最終 directory が既に存在すれば上書きせず拒否します。処理中の staging directory は失敗時に削除されます。`terminal/strata_control/local_engine.py:153-178`。
- engine が serving 中の場合は、共通 `--wait` の指定や対話状態に応じて待機確認を行い、切替が完了するまで serving engine は維持されます。待機後も busy なら切替に失敗します。`terminal/strata_cli/update_cmd.py:425-434,500-515`、`terminal/strata_control/engine_library.py:211-228`。
- 作成した local package は unsigned で、利用者が選択した間だけ起動対象になります。`STRATA_REQUIRE_SIGNED_COMPONENTS` が有効なら、package copy は完了しても切替時の署名検査で拒否され、コピーが components folder に残る場合があります。`strata components use newest` で release engine の自動追従に戻れます。`terminal/strata_control/local_engine.py:7-10,153-177`、`terminal/strata_control/engine_library.py:296-312`。

## 出力とエラー

成功時の human 出力は追加した version / folder と unsigned build である旨を表示します。`--output json` または `jsonl` では成功結果を JSON として stdout に出力します。`terminal/strata_cli/update_cmd.py:425-442`。

folder 不正、family 不明、既存 package などの拒否は主に終了コード `2`、platform / hardware 不一致や engine の起動不能は `5` です。backend 選択に関するエラーを含む失敗は human 出力なら stderr に `strata: ...`、machine output なら JSON の error object に出ます。`terminal/strata_control/local_engine.py:35-38,132-157`、`terminal/strata_cli/update_cmd.py:307-312,430-433,374-386`。

## 根拠

- parser と option scope: `terminal/strata_cli/update_cmd.py:47-56,95-99`。共通 `_common` が `add-build` parser に `--backend` を登録します。
- command dispatch と引数の受け渡し: `terminal/strata_cli/cli.py:2210-2212`、`terminal/strata_cli/update_cmd.py:314-321,425-434`。
- backend metadata の推定・優先順位・検証、build copy、manifest 作成: `terminal/strata_control/local_engine.py:77-93,127-178`。
- OS/backend 対応条件: `terminal/strata_control/targets.py:25-31,48-57`。
- unsigned package の署名条件: `terminal/strata_control/engine_component.py:386-394`。
- serving 中の切替待ち・拒否: `terminal/strata_cli/update_cmd.py:500-515`、`terminal/strata_control/engine_library.py:211-228`。
