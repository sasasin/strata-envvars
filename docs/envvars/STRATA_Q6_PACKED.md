# `STRATA_Q6_PACKED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP 系および SYCL のネイティブ Q6_K 行列ベクトル積で、ネイティブ出力ヘッドと MTP draft head の重みを、通常の GGUF ブロック配置から planes 配置へ追加コピーし、その登録済みコピーを使う経路を有効にする。設定値だけでは全 Q6_K 行列が対象になるわけではなく、実際に pack されるのは type 14 の出力ヘッドと、そこから切り出す MTP draft head。一般のモデル重みを一括変換する設定ではない（`engine/src/core/native_head.cpp:262-264`、`engine/src/core/mtp.cpp:988-995`、`engine/sycl/src/core/native_head.cpp:91-96`、`engine/sycl/src/core/mtp.cpp:855-872`）。

## 値と判定

CUDA/HIP 実装・SYCL 実装とも `native_q6_k_packed_enabled()` が初回呼び出し時に `std::getenv` の値を読み、文字列全体がちょうど `"1"` の場合に限り有効とする。空文字、`"0"`、`"true"`、`"1x"`、`" 1"`、`"01"` は無効。数値変換や trim、大文字小文字変換はしない。未設定も無効（`engine/src/kernels/cuda/native_mmvq.cu:3145-3151`、SYCL は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP または SYCL のネイティブ Q6_K 実装 | 無効。ただし後述の AMD アーキテクチャ既定値が未設定時に `1` を注入する場合がある | `1` のみ | 空文字、`0`、`true`、`1anything`、空白付きの値など、`1` と完全一致しない値 |

設定有無と値判定は異なる箇所もある。AMD 既定値注入は `getenv(...) != nullptr` で設定の有無を見ており、空文字を含む明示値があれば既定値を注入しない。その後の機能判定では空文字は無効になる（`engine/src/core/arch_defaults.cpp:307-310,318-323`）。`generate.cpp` の DFlash2 head 共有見積もりも `getenv(...) == nullptr` を条件に使うため、空文字でも共有見積もりを抑止する（`engine/src/program/generate.cpp:8406-8410`）。

## 有効になる条件

- 有効値であることに加え、ネイティブヘッドがロードされ、その GGUF type が Q6_K（type `14`）であること。CLI の `--native-head-gguf PATH` は `--stream-token` が必要で、複数 GPU 経路ではこの指定による native head load を行わない（`engine/src/program/generate.cpp:1262,3927,5380,8391-8399`）。MTP draft head についても、MTP の bind で Q6_K draft head が作られる必要がある（`engine/src/core/mtp.cpp:988-995`）。
- pack は `weights != nullptr`、`n_in > 0`、`n_in % 256 == 0`、`n_in / 256 >= WARPS * WARP / 32`、`n_out >= 2048` の全条件を満たす場合だけ試行される。既に registry にある重みなら再 pack せず成功扱いにする（`engine/src/kernels/cuda/native_mmvq.cu:3153-3157`、SYCL は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3197`）。
- CUDA/HIP の AMD アーキテクチャ既定値は、gfx1151 では `STRATA_GFX1151_DEFAULTS` が先頭文字 `0` でなく、`STRATA_DEFAULTS=026` の旧テーブル選択でない場合に既定表へ `STRATA_Q6_PACKED=1` を含む（`engine/src/core/arch_defaults.cpp:28-29,64-66,79-81`）。gfx1100/1101/1102 の discrete RDNA3 は `STRATA_GFX11_DEFAULTS=0` 等で無効化されず、明示値が未設定なら既定値表から注入する（`engine/include/strata/core/gfx11_extra.hpp:41-58`、`engine/src/core/arch_defaults.cpp:312-323`）。この注入は HIP ビルドの起動処理から呼ばれる（`engine/src/program/generate.cpp:4287-4291,4320`）。
- gfx1103（Linux のみ）および gfx1150 は、experimental opt-in が有効な setup 経路で `terminal/strata_control/setup_config.py` が `env` 設定へ `"1"` を書く。既定では opt-in は有効で、setup の環境変数 `STRATA_EXPERIMENTAL_GFX1103=0` / `STRATA_EXPERIMENTAL_GFX1150=0` で無効化される（`terminal/setup.py:4454-4459,4472-4485`、`terminal/strata_control/setup_config.py:452-465`）。これらのカードは engine の arch-default 表ではなく setup の config が既定値を供給する。
- gfx12 の arch-default 表にはこの変数がなく、NVIDIA の arch-default 表にもこの変数の既定値注入はない。明示的に `1` を渡した場合の機能判定とは別に、ここで挙げた AMD の自動既定値が他世代へ広がるわけではない（`engine/src/core/arch_defaults.cpp:30-63,64-90`）。
- AMD の arch-default 注入は既存環境値を尊重する。`setenv(..., overwrite=0)`（Windows は `_putenv_s`）を用い、表の値は `getenv` が null の場合だけ設定する（`engine/src/core/arch_defaults.cpp:218-223,307-323`）。一方、terminal server は親プロセス環境を複製した後、run config の `env` を上書き適用して engine を起動するため、config にこのキーがある場合は親環境の同名値より config 値が優先される（`terminal/serve/server.py:4010,4027-4028`）。対象変数用の CLI 引数による別の優先規則は確認できない。

## 実行時の詳細

`native_q6_k_packed_enabled()` は関数内 `static const bool` で値を一度だけキャッシュする。プロセス中に環境値が変わっても、最初の評価結果は更新されない（`engine/src/kernels/cuda/native_mmvq.cu:3145-3151`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`）。

有効で対象形状なら、pack 関数は Q6_K blocks を host 上で ql/qh/scales/d の planes に並べ、device memory にコピーして元 weights pointer と packed planes の対応を registry に登録する。`native_q6_k_mmvq()` は registry に対象 pointer と次元があり、かつ複数列の場合は `native_mmvq_multi_exact` が有効なときに packed kernel を使う。それ以外は packed 経路を断り、既存の Q6_K MMVQ 処理へ続く（`engine/src/kernels/cuda/native_mmvq.cu:2944-2979,3153-3182,3600-3610`、SYCL は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3945`）。

pack 条件不成立や device への確保・コピー失敗では pack 関数が `false` を返し、呼び出し側はその戻り値で失敗扱いにせず通常の Q6_K 経路を継続する。これらの失敗分岐にこの変数専用の警告ログはない（`engine/src/kernels/cuda/native_mmvq.cu:3153-3176`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3241`）。CUDA/HIP native head では packed Q6_K は pinned host memory への head spill と peer-head split の候補から除外される。また、Q6_K bit-plane head の生成も抑止される（`engine/src/core/native_head.cpp:130-136,225-227,262-271,297-300`）。

MTP draft head も pack 対象になり、`dhead_plain_` を false にする（CUDA/HIP: `engine/src/core/mtp.cpp:988-995`）。ただし `generate.cpp` の DFlash2 head 共有見積もりでは、環境変数が未設定の場合だけ共有可能と見積もるため、`STRATA_Q6_PACKED` が存在すれば空文字や無効値でもその見積もりから外れる（`engine/src/program/generate.cpp:8404-8410`）。

## ログと測定値

pack 成功時、CUDA/HIP と SYCL の実装は stderr に次の形式で出力する（`engine/src/kernels/cuda/native_mmvq.cu:3182-3183`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3251-3252`）。

```text
strata: STRATA_Q6_PACKED=1 packed the <what> (<n_out> x <n_in>, +<MiB> MiB)
```

`<what>` は `output head` または `MTP draft head`。shape 条件を満たさない場合や pack の転送・確保が失敗した場合、この成功ログは出ず、専用の失敗警告も出ない。`docs/DETAILS.md` に本変数の説明や測定値は見つからず、ここでは性能値を記載しない。

## 根拠

- 値判定・cache: `engine/src/kernels/cuda/native_mmvq.cu:3145-3151`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3091-3097`
- pack shape・allocation・成功ログ: `engine/src/kernels/cuda/native_mmvq.cu:3153-3183`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3191-3252`
- packed kernel 選択と fallback: `engine/src/kernels/cuda/native_mmvq.cu:2944-2979,3600-3610`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3945`
- native head と MTP 適用箇所: `engine/src/core/native_head.cpp:225-288`、`engine/src/core/mtp.cpp:988-995`、`engine/sycl/src/core/native_head.cpp:91-96`、`engine/sycl/src/core/mtp.cpp:855-872`
- AMD arch defaults と setup の既定値: `engine/src/core/arch_defaults.cpp:28-90,218-223,302-323`、`engine/include/strata/core/gfx11_extra.hpp:41-58`、`engine/src/program/generate.cpp:4287-4320`、`terminal/setup.py:4454-4485,7544-7547`、`terminal/strata_control/setup_config.py:452-465`
- run config の環境優先: `terminal/serve/server.py:4010-4028`
- DFlash2 共有見積もり: `engine/src/program/generate.cpp:8404-8410`
