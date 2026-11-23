# `setup.py` / `setup.sh` / `START-HERE.bat` `--gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（root） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU 番号を表す文字列。NVIDIA は `nvidia-smi` の番号、AMD は setup が列挙する番号。 |

## 役割

モデルのセットアップ時に使う GPU を1枚選びます。インストール済みモデルの通常起動では、その起動だけで使う GPU を指定します。複数 GPU でモデルを動かす設定は `--gpus`、カードごとの役割を指定する設定は `--gpu-roles` が担当します（`terminal/setup.py:11271-11280`）。

## 使い方

```sh
# セットアップ時に GPU 1 を選ぶ（<モデル名> は実際のモデル名に置き換える）
./setup.sh --setup --model <モデル名> --gpu 1

# インストール済みモデルを、今回だけ GPU 1 で起動する
./setup.sh --gpu 1

# Windows でインストール済みモデルを、今回だけ GPU 1 で起動する
START-HERE.bat --gpu 1
```

Linux wrapper は `terminal/setup.py` を実行し、Windows wrapper も同ファイルへ引数を渡します（`setup.sh:6-18,80-81`; `START-HERE.bat:8-13,49-65`）。

## 値と既定値

- `--gpu` は値を必須とし、1枚の GPU 番号を受け取ります。NVIDIA では `nvidia-smi` の番号、AMD では setup が表示する番号を使います（`terminal/setup.py:11271-11272`）。
- parser 後に、カンマを含む値は `--gpus` の値として扱われます。したがって `--gpu 0,1` は複数 GPU 指定として解釈され、`--gpu` 自体の単一 GPU 指定にはなりません。カンマを含まない値は前後の空白を除いた後に数字か確認され、数字でなければ usage error になります（`terminal/setup.py:11424-11430`）。
- `--gpu all` は受理されません。全カードや複数カードを選ぶ場合は `--gpus all` または `--gpus 0,1` を使います（`terminal/setup.py:11424-11430,2184-2198`）。
- 省略時、セットアップでは複数カードを共有利用できる環境なら選択画面を出し、そうでなければ利用可能なカードのうち VRAM が最も大きいものを選びます（同量なら番号が小さい方）。インストール済みモデルの通常起動では保存済みの選択が使われ、複数カードを共有可能な場合は選択を尋ねる経路があります（`terminal/setup.py:2298-2319,11503-11507`）。

## 実行時の動作

- **インストール済みモデルの通常起動:** `--gpu N` は `start()` に渡され、選択カードが検証された後、server 起動引数へ `--gpu N` として渡されます。ここでは「この起動だけ」の指定で、`--gpu` の値をモデル設定に保存する処理はありません（`terminal/setup.py:11503-11507,11540-11545,8554-8568`）。起動処理は server 用 subprocess を組み立てます（`terminal/setup.py:8517-8518`）。起動ルーチンは利用したモデル設定の更新日時を記録しますが、GPU 指定自体は保存しません（`terminal/setup.py:8512`）。
- **モデルのセットアップ:** NVIDIA では選択した番号が `GPU_PICK` に入り、セットアップ中の GPU 情報取得と engine 更新対象の選定で優先されます（`terminal/setup.py:11662-11668,2579-2592,6317-6324`）。作成するモデル設定にも `gpu` として保存され、次回起動時の既定になります（`terminal/setup.py:9905-9907,10297-10299,10722-10724`）。
- `--gpu` と `--gpu-roles` を同時に指定すると usage error になります。複数 GPU の `--gpus` が同時に指定された場合、NVIDIA セットアップの選択関数では `--gpus` が先に処理されます（`terminal/setup.py:11431-11450,2298-2307`）。

## 適用条件と副作用

- NVIDIA では指定番号が検出済みカードに存在し、setup が利用可能と判定できる必要があります。AMD では選択番号が検出済みかつ対応 backend で利用可能である必要があります（`terminal/setup.py:2201-2227,11619-11629,4976-5007`）。
- セットアップ時は選択カードに応じて GPU メモリ見積もりや engine の対象が変わり、作成するモデル設定ファイルに GPU 選択を書き込みます（`terminal/setup.py:11662-11680,9905-9907`）。通常起動時は engine にカードを渡してモデルを起動します。`--gpu` 単独では複数カードへの分割を指定しません。
- macOS の通常経路は `terminal/setup.py` の共通 parser より前に `engine/metal/setup_mac.py` の parser へ委譲されます。この別スコープの parser に `--gpu` は索引登録されていません（`terminal/setup.py:11218-11219`; 索引のスコープは `docs/cli/README.md:1652-1719`）。Hy4-Flash / Inkling-2-Mini の Mac 経路は共通 parser を通りますが、Apple GPU を index `0` として固定してセットアップ関数に渡すため、指定番号による選択はしません（`terminal/setup.py:11150-11171,11174-11195`）。

## 出力とエラー

- 数値でない値（例: `--gpu all`）は argparse の usage error になります（`terminal/setup.py:11424-11430`）。
- NVIDIA の番号が見つからない、またはカードが利用不能の場合、検出カード一覧や代替指定のヒントを表示して setup を終了します（`terminal/setup.py:2201-2227,2585-2589`）。setup 内の `fail()` はエラーを表示し、終了コード `1` を返します（`terminal/setup.py:1049-1056`）。AMD の番号が未検出または未対応の場合も、利用可能カードの案内とともに `fail()` になります（`terminal/setup.py:11623-11625,4999-5007`）。

## 根拠

- `terminal/setup.py:11271-11280` — parser 定義と `--gpu` / `--gpus` / `--gpu-roles` の役割・既定動作。
- `terminal/setup.py:11424-11450` — 値の正規化・validation、役割指定との排他。
- `terminal/setup.py:2184-2227,2298-2319` — 複数指定の parse、カード検証、セットアップ時のカード選択。
- `terminal/setup.py:11503-11507,11540-11545,8517-8518,8554-8568` — 通常起動時の一時指定と server 起動引数への転送。
- `terminal/setup.py:11619-11629,11662-11680,9905-9907,10297-10299,10722-10724` — GPU 選択とセットアップ時の設定保存。
- `terminal/setup.py:2579-2592,6317-6324` — 選択 GPU の情報取得と engine 更新対象への反映。
- `terminal/setup.py:11218-11219`; `setup.sh:6-18,80-81`; `START-HERE.bat:8-13,49-65` — macOS の委譲経路と Linux / Windows wrapper。
