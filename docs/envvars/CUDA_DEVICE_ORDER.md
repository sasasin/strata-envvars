# `CUDA_DEVICE_ORDER`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。外部ライブラリ・GPU driver の環境変数解釈は対象外。

## 役割

Strata はこの変数を二つの用途で扱います。GPU 指定を伴う engine 起動では、Strata 自身が子プロセス環境に `PCI_BUS_ID` を設定します。また NVIDIA の可視 GPU 番号を Strata が取得したカード一覧と対応付けるとき、番号の対応が明確かどうかを判定する材料として値を読みます。値の外部ランタイム上の効果はここでは扱いません。

## 値と判定

Strata の Python 判定箇所では、同じ文字列比較ではありません。

| 箇所 | 判定 | unset・空文字・その他の値 |
|---|---|---|
| `strata_control.gpu_roles.env_visible()` | `str(env.get("CUDA_DEVICE_ORDER") or "").strip().upper() != "PCI_BUS_ID"` | unset、空白のみ、その他の文字列は PCI 順として扱わない。前後空白を除き、大文字小文字を無視して比較する。 |
| `serve.server.visible_device_order()` | `(env or {}).get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID"` | unset、空文字、空白付き、小文字など、完全一致しない値は順序を確定できない扱い。 |
| C++ engine の `--gpu LIST` 起動 | 値を読み取らず `PCI_BUS_ID` を設定 | 既存値にかかわらず上書きする。 |

`gpu_roles.env_visible()` が順序判定に失敗して `None` を返すのは、NVIDIA の `CUDA_VISIBLE_DEVICES` が unset/空でなく、カードが複数あり、カードが同型・同 VRAM ではない場合に限ります。その他のケースではこの変数の値で結果を変えず、通常の可視デバイス一覧処理へ進みます。

## 有効になる条件

- **NVIDIA GPU role / split の環境可視性判定:** `CUDA_VISIBLE_DEVICES` に非空値があり、候補カードが複数で、同一モデル・同一 VRAM のカード群ではないとき、`CUDA_DEVICE_ORDER` が `PCI_BUS_ID`（前後空白除去・大文字化後）でなければ、数値の可視一覧を OS カード番号に対応付けられないとして不明扱いになります。`visible_cards()` は不明扱いの場合にカードを全件返し、split-engine 側も全カードを残します。この判定は CLI の GPU role 表示と、指定 GPU のない split-engine の候補選びに使われます。
- **server の topology 表示用対応付け:** backend が `None` または `cuda` で、環境辞書の値が文字列として正確に `PCI_BUS_ID` の場合にだけ、CUDA 可視リストを `visible_device_order()` が数値リストへ変換します。該当しない場合は空リストになり、server は engine ordinal を OS GPU index へ対応付けられません。HIP backend はこの変数を条件にせず HIP 可視リストを扱います。
- **Engine の `--gpu LIST`:** 起動引数に値付き `--gpu` が見つかった場合、engine は最初の該当引数を処理するループ内で、CUDA build でも HIP build でもこの変数を `PCI_BUS_ID` に設定します。`--gpu` がない場合、ここでの設定はありません。

## 実行時の詳細

`serve.server.child_env()` は親の `os.environ` をコピーし、GPU を選択する CUDA 経路では `CUDA_DEVICE_ORDER=PCI_BUS_ID` を入れてから `cfg["env"]` の各項目を反映します。そのため profile の `env` に同名キーがあれば、server が加えた値を上書きできます。HIP 可視 GPU を設定する分岐自体はこの値を設定しません。Vision 用の CUDA GPU 指定も `vision_env()` で `PCI_BUS_ID` を設定します。画像 runner の `image_env()` も CUDA GPU 指定後に config の `env` を反映するため、同じ上書き順です。参照: `serve/server.py:4325-4338,4509-4524`; `serve/images.py:142-160`。

C++ engine では `main` の初期化中に `--gpu` を走査し、既存の可視デバイス環境と指定値が異なる場合は `CUDA_VISIBLE_DEVICES` または HIP build の `HIP_VISIBLE_DEVICES` について警告した後、`CUDA_DEVICE_ORDER` と可視デバイス変数を設定します。コメントは CUDA 呼び出しより前の設定が必要としています。値が空のときや既存値が CLI 値と同じときは、その警告条件に入りません。この警告は `CUDA_DEVICE_ORDER` の値に対するものではありません。参照: `src/program/generate.cpp:3321-3342`。

Python の `env_visible()` は引数 `environ` があればその辞書を、なければ呼び出し時点の `os.environ` を参照します。`visible_device_order()` は渡された環境辞書をそのまま判定し、server は起動時に構築した子環境を渡して `terminal_visibility_order` を保持します。これらの関数に独自の static cache はありません。参照: `strata_control/gpu_roles.py:453-476`; `serve/server.py:1023-1034,10359`。

## ログ・失敗経路

順序が不明な場合、上記の Python 関数は空/不明の対応表へ fallback し、`visible_cards()` と split-engine は候補カードを絞りません。確認した呼び出し経路に、この変数の不一致だけを理由とする警告・終了・例外はありません。engine の `--gpu` が出す警告は、別変数である可視デバイス設定の上書きについてです。

## 根拠

- `strata_control/gpu_roles.py:453-484` — 環境辞書の選択、NVIDIA 条件、文字列正規化、不明時のカード全件 fallback。
- `strata_cli/launch/cmd.py:475-492` — `visible_cards()` を GPU role の表示に使う呼び出し元。
- `strata_control/split_engine.py:366-375` — 指定 GPU がない split-engine の候補絞り込み。
- `serve/server.py:1023-1034,4325-4338,4509-4524,10359` — topology ordinal の判定、engine/Vision 子環境の作成と起動時の保持。
- `serve/images.py:142-160` — 画像 runner 環境での設定および config 環境値の適用順。
- `src/program/generate.cpp:3321-3342` — `--gpu` 指定時の C++ 側設定と可視デバイス上書き警告。
