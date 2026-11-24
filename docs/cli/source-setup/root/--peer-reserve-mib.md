# `--peer-reserve-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers |
| オプション | `--peer-reserve-mib` |
| 別名 | なし（source-setup の parser 上） |
| 値 | 整数 MiB。setup.py の parser は `int` に変換する |

## 役割

Qwen3.6-35B-A3B を CUDA の2 GPUでセットアップするとき、2枚目の GPU に置く expert tier のために確保する VRAM の空き量を MiB で指定します。値は setup.py が生成する起動設定の engine 引数へ渡され、tier の割り当て可能量を調整します。setup.py のヘルプに示される engine 側の既定値は 600 MiB です。

## 使い方

```sh
# Qwen3.6 を2 GPU構成で設定し、peer GPU に 1024 MiB を空ける。通常のセットアップ処理を行い、--no-start により最後の起動はしない。
python3 terminal/setup.py --family qwen36 --gpus 0,1 --peer-reserve-mib 1024 --no-start
```

`--gpus` の指定順にかかわらず setup.py が選ぶ main GPU と peer GPU の対応に従います。セットアップ自体はモデル等の準備と起動設定の書き込みを行います。

## 値と既定値

- 値は必須で、setup.py は `argparse` の `type=int` を指定しています。整数でない値は parser で拒否されます。
- setup.py 側には非負値などの範囲検証がありません。省略時は setup.py からこの値を engine に渡さず、Qwen3.6 engine の既定値 600 MiB が使われます。
- engine は確保量の計算で `max(0, 値)` を使うため、負数は 0 MiB として計算されます。明示的な上限値の検証は確認できません。

## 実行時の動作

- setup.py は `--peer-reserve-mib` を parser に登録します。Qwen3.6 の own-path セットアップで CUDA の2 GPUが選ばれた場合に限り、生成する engine 引数へ `--peer-device 1` とともに値を追加します。設定の `gpu` 配列も main GPU、peer GPU の順に書きます。
- engine は値を `peer_reserve_mib` に保持します。peer GPU の空き VRAM を `cudaMemGetInfo` で取得し、予約量を差し引いた予算から expert slot 数を計算します。したがって値を大きくすると tier 用 slot に使える VRAM が減ります。slot 数は残りの expert 数にも制限されます。
- このオプションは setup.py の他の family や、peer GPU が選ばれない構成では engine 引数に転送されません。setup.py の parser はオプション自体を受理しますが、その構成での別の効果は確認できません。

## 適用条件と副作用

- setup.py の説明上の対象は Qwen3.6-35B-A3B の2 GPU構成です。実装では `multi` に2 GPUがあり、かつ HIP でない場合に peer GPU を選びます。HIP で複数 GPU が指定された場合などは peer tier を設定せず、GPU 構成について警告して単一 GPU を使う分岐があります。
- 値は生成される run config の engine 引数として保存され、通常のセットアップ処理の副作用（モデル準備、設定・起動スクリプトの書き込み）は伴います。`--no-start` は setup.py の最後の起動を抑止しますが、これらの準備処理は抑止しません。
- engine が tier を開く際、peer GPU の空き VRAMから予約 MiB を引きます。予算で expert slot を1つも確保できないと peer tier の初期化は失敗します。予約値のほか、実際の空き VRAM や expert buffer の確保可否も結果に関わります。

## 出力とエラー

- setup.py の `int` 変換に失敗する値は `argparse` の引数エラーになります。
- engine は peer GPU の空き VRAM取得失敗、slot を確保できない場合、または tier の `cudaMalloc` 失敗をエラー文字列にし、expert 配置失敗時に stderr へ `strata-q36:` を付けて出力して終了コード 1 を返します。slot 不足時の文言には空き VRAM と予約 MiB が含まれます。
- tier を開けた場合は、割り当てた expert 数・VRAM量と予約値を stderr に出力します。

## 根拠

- `terminal/setup.py:11575-11577` — setup.py parser の型、値の説明、engine の既定値。
- `terminal/setup.py:9833-9851` — own-path セットアップが Qwen3.6 の peer GPU を選ぶ条件と、対象外構成での警告。
- `terminal/setup.py:9984-10008` — engine 引数への値の転送、および main/peer GPU 配列の設定。
- `terminal/setup.py:10044-10059` — run config と起動スクリプトの書き込み、`--no-start` 時の分岐。
- `engine/src/qwen35/q36_engine.cu:1621-1623` — engine の既定値 600 MiB。
- `engine/src/qwen35/q36_engine.cu:5388-5391`、`5470-5473` — engine parser による受理と Engine への設定。engine 側には `--peer-reserve` alias もあるが、source-setup は canonical 名のみ転送する。
- `engine/src/qwen35/q36_engine.cu:4126-4144` — 空き VRAMから予約を差し引く計算と slot 不足時の失敗条件。
- `engine/src/qwen35/q36_engine.cu:4146-4154`、`4240-4244` — tier の VRAM 確保失敗経路と成功時の stderr 出力。
- `engine/src/qwen35/q36_engine.cu:5522-5525` — expert 配置失敗時の stderr 出力と終了コード 1。
