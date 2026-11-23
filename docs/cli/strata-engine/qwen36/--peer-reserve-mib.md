# `--peer-reserve-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 モデル選択時）または `strata-q36` |
| オプション | `--peer-reserve-mib` |
| 別名 | `--peer-reserve` |
| 値 | 整数 MiB |

## 役割

`--peer-device` で指定した2枚目の CUDA device に routed expert を置く際、その device で空けておく VRAM 量を MiB で指定します。値は peer tier の slot 数を見積もる予算から差し引かれます。単独では peer tier を有効にせず、`--peer-device` が device 1 以上を指定していることが必要です。

## 使い方

```sh
# Qwen3.6 を strata-q36 で実行し、CUDA device 1 に 800 MiB を残して expert を配置する
strata-q36 --model ./Qwen3.6-35B-A3B.gguf --peer-device 1 --peer-reserve-mib 800 --tokens 1,2,3
```

索引上、この Qwen3.6 専用 parser は `strata` から Qwen3.6 モデルを選択した場合にも使われます。`strata-q36` の実行ファイルと `strata` の切替先はいずれも `engine/src/qwen35/q36_engine.cu` の `strata::qwen35::run` です（同ファイル先頭コメントおよび `engine/src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- 省略時は `600` MiB です（`engine/src/qwen35/q36_engine.cu:5341-5343`）。
- `--peer-reserve-mib N` と alias の `--peer-reserve N` は同じ整数変数に読み込まれます。後に指定した値が前の値を上書きします（`engine/src/qwen35/q36_engine.cu:5388-5391`）。
- 引数がない場合は `strata-q36: --peer-reserve-mib needs a value`（alias 使用時はその alias 名）を stderr に出し、終了コード `2` で終了します（`engine/src/qwen35/q36_engine.cu:5350-5352`）。
- 数値変換は `std::atoi` です。専用の範囲検証や不正文字列のエラー処理はありません。peer 予算を計算するときは負値を `0` として扱います（`engine/src/qwen35/q36_engine.cu:5390`, `4129-4131`）。

## 実行時の動作

parser は値を `peer_reserve` に保存し、`Engine::peer_reserve_mib` に渡します（`engine/src/qwen35/q36_engine.cu:5390`, `5468-5473`）。expert 配置処理は card 0 の hybrid slot 数が決まった後に peer tier を開き、peer device を選択して `cudaMemGetInfo` から得た現在の空き量 `fr` を読みます。予約量を bytes に換算し、`budget = max(fr - reserve, 0)` とします。各層の expert stride 合計と末尾領域を使って配置可能な slot 数を算出し、`--peer-slots` が正ならその上限も適用します（`engine/src/qwen35/q36_engine.cu:4077-4079`, `4112-4135`, `4388-4393`）。

peer tier が開くと、算出した slot 数分の領域を peer device 上に `cudaMalloc` し、expert blob をそこへ配置します。予約量は固定量の確保を保証する指定ではなく、peer tier の算定時に空けておく目標量です。配置後には実際の slot 数、peer 上に残した MiB 量などを stderr に出します（`engine/src/qwen35/q36_engine.cu:4146-4156`, `4239-4244`）。

## 適用条件と副作用

- `--peer-device` の既定値は `-1` で、値が `1` 未満なら peer tier 初期化は何もせず成功します。このとき本オプションは配置に影響しません（`engine/src/qwen35/q36_engine.cu:1622`, `4077-4079`）。
- card 0 に全 routed expert が収まる経路では、2枚目に置く expert がないため peer tier を開かず、本オプションは適用されません（`engine/src/qwen35/q36_engine.cu:4329-4335`, `4086-4089`）。
- peer tier で slot を確保できない（たとえば予約後の予算が不足する）場合、配置は失敗します。予約値が負でも 0 MiB として計算されます（`engine/src/qwen35/q36_engine.cu:4129-4146`）。
- 値が大きいほど peer tier の slot 数が減る可能性があります。peer 上の GPU メモリをこのオプション自身が別用途で確保するわけではありません。
- `--peer-device` 指定時は card 0 側の hybrid 配置計画でも portable pinned mapping 等のための headroom が 96 MiB から 192 MiB に増えます。これは本オプションの予約量とは別の card 0 向け計算です（`engine/src/qwen35/q36_engine.cu:4365-4370`）。

## 出力とエラー

peer device が存在しない場合は `--peer-device N: no such CUDA device`、メモリ情報を取得できない場合は `--peer-device N: cudaMemGetInfo failed`、expert slot を置けない場合は空き MiB と予約 MiB を含む `--peer-device N: no room for an expert slot (...)` がエラー文字列になります（`engine/src/qwen35/q36_engine.cu:4121-4146`）。これらは配置処理の失敗として呼出し元で `strata-q36: <エラー>` の形で stderr に出され、終了コード `1` になります（`engine/src/qwen35/q36_engine.cu:4388-4393`, `5523-5525`）。CUDA allocation の失敗も同様に配置エラーになります（`engine/src/qwen35/q36_engine.cu:4148-4155`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5341-5414` — Qwen3.6 parser、既定値、alias、引数不足・未知引数の処理。
- `engine/src/qwen35/q36_engine.cu:1621-1622`, `5468-5473` — Engine の既定値と parser 値の受け渡し。
- `engine/src/qwen35/q36_engine.cu:4077-4155` — peer tier の適用条件、空き VRAM と予約値からの slot 算定、失敗経路、peer device 上の領域確保。
- `engine/src/qwen35/q36_engine.cu:4239-4244`, `4365-4393`, `4540-4548` — 出力、card 0 側の headroom、配置から peer tier を呼ぶ順序。
- `engine/src/qwen35/q36_engine.cu:5523-5525` — 配置失敗時の stderr 表示と終了コード。

調査範囲はこの checkout の Qwen3.6 parser とその peer expert 配置経路です。GPU 実行や `--help` は行っていません。
