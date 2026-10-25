# `STRATA_PRIMARY_DEVICE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`strata generate` がモデルと通常の実行セッションを置く可視 GPU の ordinal を指定します。未設定または 0 は従来どおり ordinal 0 を使います。主 GPU の選択は `--expert-cache-device1..3` の補助キャッシュ GPU の割り当てや、peer GPU の相互アクセス判定にも使われます。実装コメントは特に Windows HIP の固定列挙順を理由として挙げています。`HIP_VISIBLE_DEVICES` はデバイスを絞りますが Windows HIP の列挙順を変えないため、より速い GPU が後ろにある場合に本変数で主 GPU を選べます。

## 値と判定

起動時に `std::getenv` で値を一度読み、`std::atoi` で整数に変換します。変換後の値が正の場合だけ採用し、それ以外は 0 にします。文字列全体の妥当性確認はありません。

| 環境値 | 結果 |
|---|---|
| 未設定 | 0 |
| 空文字、数値に変換できない文字列 | 0（`atoi` が 0 を返す） |
| 正の整数 | その整数。例: `2`、`+2` |
| 正の整数の後ろに文字が続く値 | 数字部分の整数。例: `2abc` は 2 |
| 0 または負の数 | 0 |

`atoi` のため、先頭空白の後の符号付き数字も変換対象です。範囲外の数値に対する `atoi` の結果は C/C++ の仕様上保証されないため、ここでは動作を規定しません。設定有無だけを判定する方式ではなく、空文字は有効な ordinal になりません。

根拠: `src/program/generate.cpp:2740-2749`。

## 有効になる条件

- 値の読み取りは `generate.cpp` の生成処理で行われます。別プロセスから呼び出す場合は、そのプロセスの環境に設定されている必要があります。リクエストごとの再読込を示す実装はなく、生成処理の起動時に一度評価されます。
- 正の ordinal は可視デバイスの範囲内でなければなりません。`cudaGetDeviceCount` が失敗するか ordinal が可視台数以上の場合は stderr に `strata generate: STRATA_PRIMARY_DEVICE=%d: no such visible device (%d visible)` を出して終了コード 2 で戻ります。
- 範囲内でも `cudaSetDevice` が失敗すると stderr にエラー理由を出し、終了コード 1 で戻ります。成功時は stderr に `strata generate: primary device from STRATA_PRIMARY_DEVICE: CUDA%d` を出します。0 の場合、この切り替え、検査、成功ログは行いません。
- `--layer-split` が空でない状態では、主 ordinal が 0 以外なら layer split の準備後に stderr へ `strata generate: STRATA_PRIMARY_DEVICE %d is not supported with a layer split yet` を出して終了コード 2 で戻ります。split が auto でもこの時点で有効な指定として残っていれば拒否されます。
- これは CUDA/HIP 共通の生成コードにあり、ソース上で Windows HIP 専用の環境値判定には限定されていません。ただし Windows HIP 以外での必要性や具体的な列挙順は、環境やランタイムに依存するため本コードだけでは一般化できません。

## 実行時の詳細

読み取った ordinal は `strata::core::set_primary_device()` に保存されます。同実装はプロセス内の整数を設定・返却するだけです。ordinal が正なら、GPU コンテキストや割り当てが始まる前に生成スレッド上で `cudaSetDevice(primary_device)` を呼びます。失敗時には上記のエラーで処理を止めます。このため、その後の主セッション用 GPU 作業は指定したデバイスを基準に開始します。セッション生成時も `OnDevice(primary_device)` が使われます。

補助 expert cache の配置は、主デバイスが 0 の場合は既定の `{1, 2, 3}` です。主デバイスが 0 以外なら可視 ordinal を昇順に見て主デバイスを除外し、最大 3 台を補助デバイスとして選びます。主デバイスと同じデバイスを補助 cache として開こうとした場合、`RemoteExperts::preflight` はエラーにします。peer expert cache は `primary_device()` と補助デバイス間の双方向 peer access の問い合わせ・有効化に主 ordinal を使います。

環境値は `generate.cpp` のこの処理で一度だけ読みます。設定値の変更を実行中に反映する再読込や、子プロセスへの書き換えはこの実装箇所にはありません。`CUDA_VISIBLE_DEVICES` / `HIP_VISIBLE_DEVICES` がある場合の ordinal は、ランタイムが列挙する可視デバイスの ordinal です。

## 根拠

- 環境値の読み取り、`atoi`、正数以外を 0 にする処理、グローバルへの設定: `src/program/generate.cpp:2740-2749`、`src/core/device.cu:87-92`。
- layer split との併用拒否: `src/program/generate.cpp:2811-2819`。
- 補助 GPU の選択: `src/program/generate.cpp:2837-2849`。
- 主 GPU の検証、切り替え、ログ: `src/program/generate.cpp:3262-3280`。
- 主 GPU に置くセッション: `src/program/generate.cpp:4937-4943`。
- 主 GPU と補助 cache の重複拒否: `src/core/remote_experts.cpp:69-80`。
- peer GPU 判定・有効化に使う ordinal: `src/core/peer_experts.cpp:138-151`。
- Windows HIP の選択理由と利用者向け説明: `include/strata/core/device.hpp:51-57`、`docs/SECOND_GPU.md:210-225`。
