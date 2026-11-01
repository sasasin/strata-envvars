# `setup.py --vision`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper からの委譲先） |
| オプション | `--vision` |
| 別名 | なし |
| 値 | `yes`、`no`、`none`、`gpu`、`cpu` のいずれか（値必須） |

## 役割

モデルの画像入力を有効にするか、画像 encoder を GPU と CPU のどちらで動かすかを setup に指定します。効果はモデル family と backend によって異なります。省略時は parser 上 `None` であり、setup が対話質問、モデルごとの既定、または既存設定の引き継ぎを適用します。

## 使い方

```bash
./setup.sh --vision cpu
```

Windows では同じ parser を使う `START-HERE.bat --vision no` が使えます。どちらも wrapper が引数を `setup.py` に渡します（`setup.sh:1-8`、`START-HERE.bat:1-15`）。

## 値と既定値

- `yes`: 画像を有効にし、その経路の自動選択規則で reader を決めます。Flash-Next など通常の画像 encoder 経路では、VRAM が 23.5 GB 未満なら CPU、それ以外（VRAM を取得できない場合を含む）は GPU です（`setup.py:3384-3401`）。Qwen3.6 own-path では AMD は `vision_reader` の既定規則へ渡し、非 AMD は同じ 23.5 GB 判定を使います（`setup.py:7830-7859`）。
- `gpu`: GPU reader を要求します。Flash-Next の NVIDIA 経路では小容量カードでも選択を維持し、VRAM を使う旨を警告します。AMD では希望として扱い、実際に利用可能な HIP reader がなければ CPU reader へ fallback する場合があります（`setup.py:3389-3401`、`4842-4848`、`4865-4873`）。
- `cpu`: CPU reader を指定します。通常の画像 encoder 経路では CPU 用 thread 数を設定に記録します（`setup.py:8090-8096`、`10421-10431`）。
- `no` と `none`: 通常の画像 encoder 経路および Qwen3.6 own-path では画像を無効にします（`setup.py:7835-7838`、`9797-9799`）。DeepSeek-V4.1 の専用経路は `no` を無効値として扱いますが、`none` は無効扱いせず画像を有効にします（下記「適用条件と副作用」）。
- 明示値がない場合の一律な parser default はありません。Flash-Next 等の標準経路は画像について質問し、画像対応モデルでの既定回答を使います。Qwen3.6 own-path は質問し、既定回答は yes です。`--yes` を併用すると質問を省き、その既定回答を選びます（`setup.py:7839-7851`、`9797-9813`）。新しいコピーが既存設定を採用する場合は、明示値がなければ以前の `vision` 設定を引き継ぎます（`setup.py:9282-9295`）。

## 実行時の動作

標準の画像 encoder 経路では、画像を有効にすると `mmproj` encoder ファイルを既存配置から探すかダウンロードし、設定 JSON に encoder 実行ファイル・encoder/model のパス・GPU 使用有無・画像 token 上限を書きます。無効ならこの設定を作らず、画像関連引数も追加しません（`setup.py:8040-8049`、`8085-8098`、`10421-10433`）。`--vision-tokens` は併用可能な別 option で、画像が無効なら警告して使われません（`setup.py:8097-8098`）。

標準の Flash-Next 系では、指定値は encoder の方式に反映されます。AMD HIP 経路では engine folder にある reader を確認して最終 mode を決めます。指定した GPU reader が engine にない場合などの詳細は `vision_reader` が決め、setup は返された注記を警告として表示します（`setup.py:9946-9950`、`4865-4873`）。

## 適用条件と副作用

- モデルが画像入力非対応の場合、設定は `none` に補正され、画像を明示的に要求したときは「このモデルでは利用できない」旨を警告します（`setup.py:9789-9792`）。
- DeepSeek-V4.1 は別の内蔵 vision tower を使います。画像は既定で有効で、`--vision no` のときだけ pack 用の共有 `mmproj` を外して text-only にします。`gpu` と `cpu` は「yes」と同じ画像オンとして警告され、専用 reader の選択にはなりません。`none` も `no/off` の判定に含まれないため画像オンです（`setup.py:8544-8551`、`8604-8607`）。macOS でこの専用経路の reader が未対応の場合は、値にかかわらず画像を無効にする警告があります（`setup.py:8546-8549`）。
- preview family `qwen36` は、この Strata 版では起動設定を作りません。`yes`、`gpu`、`cpu` の明示時に限り encoder ファイルをダウンロード対象に含め、`no` / `none` / 省略時は含めません（`setup.py:8784-8787`、`8802-8826`）。
- 通常経路で encoder を必要とするのに選択済み engine に `strata-vision` がない場合、setup は警告して画像をオフにします。CUDA 等の通常経路では「`--build` で再実行して compile」と案内します（`setup.py:7790-7798`、`8020-8025`）。AMD では reader が使えない場合に CPU reader へ切り替える可能性があります。
- `setup.py` の通常 parser は `none` を受理します。一方、Apple Silicon の非 Control 実行は parser を作る前に `metal/setup_mac.py` へ委譲され、その parser の選択肢は `yes/no/gpu/cpu` で `none` を受理しません。Mac 側は `cpu` 以外を yes に正規化します（`setup.py:9068-9070`、`metal/setup_mac.py:353-358`、`404-410`）。この別 parser の詳細は索引の `source-setup/mac/--vision.md` scope です。
- 有効化すると setup は encoder の追加ダウンロードまたは既存 encoder の使用を行い、モデル設定 JSON と起動 script を更新します。通常経路では setup 完了後にその設定で起動します（`setup.py:8040-8049`、`10421-10431`、`10453-10490`）。

## 出力とエラー

選択した mode は `images: off/on` 等の確認行に表示されます。低 VRAM で GPU reader を指定した場合や、DeepSeek-V4.1 で `gpu/cpu` を指定した場合は警告が出ます（`setup.py:7856-7859`、`8604-8607`）。通常 parser で選択肢以外の値を渡すと `argparse` が usage とエラーを表示して終了します。encoder の不足、download/検証失敗などの後続失敗は該当 setup 処理で発生し、この option 固有の独立した終了コードは定義されていません。

## 根拠

- Parser と選択肢: `setup.py:9089-9091`。通常 parser を作る入口と Apple Silicon 委譲: `setup.py:9068-9070`。
- 通常経路の VRAM 判定と警告: `setup.py:3384-3401`、Qwen3.6 own-path の質問・判定: `setup.py:7830-7859`。
- AMD reader の選択と fallback 情報: `setup.py:4842-4848`、`4865-4873`。
- 標準モデルの画像可否・既定値・対話選択: `setup.py:9789-9814`。
- encoder の取得と設定 JSON への反映: `setup.py:8040-8049`、`8085-8098`、`10421-10433`。
- DeepSeek-V4.1 と preview family の差: `setup.py:8544-8551`、`8604-8607`、`8784-8826`。
- Mac 側 parser は別 scope: `metal/setup_mac.py:353-358`、`404-410`。

確認範囲は上記 checkout の `setup.py`、関係する Mac setup parser、および `docs/cli/README.md` の scope 定義です。各 GPU reader の実行時互換性や外部配布 encoder の挙動は、このソース追跡だけでは確定していません。
