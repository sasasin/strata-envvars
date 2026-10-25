# `--prebuilt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`./setup.sh`、`START-HERE.bat` などからも同じ parser を使用） |
| オプション | `--prebuilt` |
| 別名 | なし |
| 値 | 既製 engine の配布 URL またはローカル folder。既定値は `STRATA_PREBUILT_URL`、未設定なら標準 Release URL |

## 役割

モデル setup が CUDA または Windows HIP の既製 Strata engine を取得するときの場所を指定します。Windows HIP ではビルド済み engine が必須です。Linux HIP はこの場所から取得せずローカル build に進みます（`setup.py:7383-7415`）。

## 使い方

Linux で、自作の CUDA engine archive を置いた folder から setup する例です。

```sh
./setup.sh --setup --prebuilt ./dist --no-start
```

Windows では `START-HERE.bat --setup --prebuilt D:\strata-dist --no-start` のように指定できます。`setup.sh` と `START-HERE.bat` は引数を `setup.py` に渡し、`SETUP.bat` / `UPDATE.bat` と `update.sh` も同じ入口へ委譲します（`setup.sh:8-12,76`, `START-HERE.bat:48-55`, `SETUP.bat:1-3`, `UPDATE.bat:75-79`, `update.sh:58-62`）。

## 値と既定値

- parser は値を一つ受け取り、`default=os.environ.get("STRATA_PREBUILT_URL", PREBUILT_URL)` で定義します。環境変数が未設定なら `https://github.com/Niko1221/Strata/releases/latest/download/` が使われます。CLI で `--prebuilt` を指定すると環境変数由来の既定値より優先されます（`setup.py:223-233,8513-8514`）。
- 値の URL/パス形式を parser では検証しません。取得関数は末尾が `/` または `\` でなければ `/` を補います。HTTP(S) 以外はローカル path として扱われ、`file://` は先頭を外して読みます（`setup.py:5001-5007,2781-2795`）。
- 標準 URL と同じ値なら、checkout のバージョン用 Release を先に確認し、その後 latest を確認します。標準 URL と異なる値はその場所だけを使います（`setup.py:5001-5007`）。空文字も受理され、取得先なしとして扱われます。
- 値の欠落は `argparse` の usage/error になります。同じ `store` option を複数回指定した場合は最後の値が残ります（`setup.py:8513-8514`）。

## 実行時の動作

- 通常 setup の CUDA 経路は `a.prebuilt` を既製 engine 取得関数へ渡します。`--build` がある場合や Linux HIP の場合は取得を迂回して build します（`setup.py:7383-7410`）。Windows HIP は同じ値を使って既製 HIP engine を取得します（`setup.py:7390-7396`）。
- `--prebuilt` はモデルや Python package の取得元を変えません。engine archive 名を取得先 folder に連結し、HTTP(S) なら `HEAD` で存在を確認してからダウンロード、ローカルならその archive file をコピーします（`setup.py:5112-5135,2781-2795`）。
- GitHub Release URL の archive は GitHub API から得たサイズと SHA-256 で検証します。ローカル folder や Release URL 以外の mirror は比較できる公開 digest がないため、警告して検証なしで続行します（`setup.py:4852-4911,4920-4981`）。
- 互換性のある既製 engine が既にインストールされている場合、取得先を調べず再利用することがあります。必要 version より古い場合は取得を試みます。archive は展開前に検証され、必要 version 未満または対象 GPU の code がない場合、通常 CUDA setup は警告して build に切り替えます（`setup.py:5087-5111,5134-5178`）。
- 明示的な `--update` は、インストール済み model があるとき、かつ `--build` がないときに `a.prebuilt` を engine 更新関数へ渡します。更新不要なら取得せず、取得に失敗した場合は既存 engine を保持して続行します。対象 model がない場合は engine 更新前に終了します（`setup.py:6682-6709,8617-8619,5235-5323`）。
- 更新対象が既にローカル build の engine なら、更新関数は source fingerprint を見て必要な場合に再 build するため、`a.prebuilt` は取得元として使われません（`setup.py:5280-5308`）。`--rollback-engine` は更新分岐より前に戻るため、この値を取得に使いません（`setup.py:8614-8619`）。
- 通常の model 起動では古い engine の通知だけを行い、network access や更新はしません（`setup.py:5208-5232,8677-8682`）。
- 起動中に Pascal/Volta GPU のため CUDA 12 engine へ切り替える経路は、`--prebuilt` の値ではなく `STRATA_PREBUILT_URL` を直接読みます。そのため、この切替に CLI 指定は引き継がれません（`setup.py:7236-7255`）。

## 適用条件と副作用

- `--prebuilt` で取得すると、engine archive を `engine/` または CUDA 12 用 `engine-cuda12/` に展開し、既存 engine を `.previous` に保持して置き換える場合があります。Linux では実行ファイルに実行権限を設定します（`setup.py:5087-5094,5170-5179,5020-5035`）。
- 標準以外の URL では flat archive の候補はその場所だけです。ただし CUDA 12 以外は候補が見つからない場合に signed update feed も試します。Windows HIP も flat archive が見つからない場合は feed を試し、利用可能な engine がなければ `fail()` で setup を停止します（`setup.py:5117-5133,4269-4317,4352-4353,7390-7396`）。
- ローカル path の archive が存在しない場合は `not found` を表示して終了コード 1 で停止します（`setup.py:2789-2795,825-830`）。通常 setup で取得した archive の検証に失敗した場合も停止し、`--update` 中なら警告して既存 engine を維持します（`setup.py:4990-4998,5134-5140`）。
- `--build` と `--update` を併用すると既製 engine 更新を省きますが、`--update` 自体は engine を compile しません（`setup.py:6682-6697`）。
- Windows HIP で `--build` を指定すると既製品の取得も抑止されますが、この setup 経路にはローカル build がなく、既製品なしとして停止します（`setup.py:7390-7396`）。
- macOS の `CONTROL` 経路は parser 後に engine component setup へ分岐し、通常の `engine_step()` を通りません。`--backend sycl` も専用 setup へ先に委譲します。これらの経路で `--prebuilt` が通常の CUDA/HIP engine 取得先として使われる処理は確認できません（`setup.py:8561-8564,7383-7388`）。

## 出力とエラー

取得時は ready-made engine の確認・ダウンロード状況を表示します。flat archive URL が見つからない場合、対象経路では signed update feed も試します。最終的に engine を取得できない、version が古い、または GPU code が不足する場合は警告を出し、通常 CUDA setup では build に進む場合があります。ローカル archive 不在や通常 setup の検証失敗では `fail()` が `[X]` と `Setup stopped` を表示し、終了コード 1 で停止します。更新中の検証失敗は既存 engine を残す警告経路です（`setup.py:4269-4317,5117-5135,5150-5169,825-830,4990-4998`）。

## 根拠

- parser、既定 URL、標準 Release URL: `setup.py:223-233,8513-8514`
- 関連する環境変数の別文書: [STRATA_PREBUILT_URL](../../../STRATA_PREBUILT_URL.md)（同文書の調査 revision は今回の checkout と異なるため、ここでは今回確認したソースを根拠にしています）
- 末尾区切り文字と URL 候補順: `setup.py:5001-5007`
- 通常 setup の backend dispatch: `setup.py:7383-7415`
- 既製 engine の再利用・取得・検証・展開と feed fallback: `setup.py:5087-5181,4269-4317`
- Windows HIP の取得と適合判定: `setup.py:4320-4394`
- `--update` と起動時の更新通知: `setup.py:5208-5323,6682-6709,8617-8619`
- local/HTTP download と失敗出力: `setup.py:2781-2795,825-830,4990-4998`
- CUDA 12 切替と特殊 setup 分岐: `setup.py:7236-7255,8561-8564`
- wrapper の引数委譲: `setup.sh:8-12,76`, `START-HERE.bat:48-55`, `SETUP.bat:1-3`, `UPDATE.bat:75-79`, `update.sh:58-62`

調査範囲は指定 checkout の `setup.py`、該当 wrapper、および索引・調査規約です。同一 revision の CLI `--help` と Release artifact の実体は照合していません。実機のダウンロード、build、GPU 実行は行っていません。
