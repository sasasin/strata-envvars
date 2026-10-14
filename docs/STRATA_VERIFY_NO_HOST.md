# `STRATA_VERIFY_NO_HOST`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL verifier の device-plan 経路で、ホストが各 layer の doorbell / flag handshake に応答しない前提を選びます。設定が有効だと、ホスト側の層ごとの応答ループを省略し、SYCL の verify window 全体をまとめて待つ経路になります。`STRATA_VERIFY_DEVICE_PLAN` による device plan 自体を有効にする変数ではありません。device plan は別途有効である必要があります。

主な実装は `sycl/src/core/verify.cpp` の window 記録・完了処理と、`sycl/src/program/generate.cpp` の起動時の安全確認です。CUDA/HIP実装に同名の実動作参照は確認できませんでした。

## 値と判定

実装は `getenv()` の値を空文字かどうか確認し、その後文字列全体を `"0"` と比較します。数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 文字列がちょうど `0` | OFF |
| 上記以外の非空文字列 | ON。例: `1`, `00`, `false`, `0abc`, 前後に空白のある値 |

そのため `00` や `false` は数値的に偽らしく見えてもONです。大文字小文字や数値としての妥当性は検査されません。verify.cpp 内の判定結果は `static const bool` にキャッシュされるため、その判定が初めて実行された後に同一プロセスの環境を書き換えても反映されません。起動処理中の安全確認は `generate.cpp` で別途評価されます。

根拠: `sycl/src/core/verify.cpp:800-801,2183-2184`; `sycl/src/program/generate.cpp:4961-4962,5061-5063`。

## 有効になる条件

- `STRATA_VERIFY_DEVICE_PLAN` 等により device plan が有効であること。`STRATA_VERIFY_NO_HOST` はそれを有効化しません。
- device-plan が必要とする expert がVRAMにあるか、device planから参照できるホストミラーにあること。初段のVRAM不足分がミラーされず `unmirrored_misses > 0` の場合、起動時に生成を拒否して終了コード2にします。
- 複数GPUのlayer splitでは、後段のstageのexpert cacheに不足があれば、後段をカバーするホストミラーがないため起動を拒否します。設定を `0` にするとホスト応答経路を許可し、不足expertをホスト側で処理できます。
- device-plan とこの変数が有効な場合、適応的なexpert swap (`--adapt-every` と `--adapt-swaps` が正) は、移動したexpertをVRAMにもミラーにも置けなくなる危険があるため無効化されます。
- `record_window()` の `STRATA_VERIFY_LEAN` 経路はさらに、step hook、remote-opt、常時publish、stepped mode がなく、device plan が有効であることを条件にします。この場合、ホストが応答しない doorbell / flag wait、plan copy、PCIe-share group とstaging kernelなど不要なgraph nodeを省略します。

## 実行時の詳細

通常のverify window完了処理は、device planでresident expertを処理する状況などを除いて、layerごとにGPUのsequence値を待ち、ホスト側のplanを公開します。`STRATA_VERIFY_NO_HOST` が有効ならこの層ごとのループ条件が成立せず、ホスト側は各layerのdoorbellに応答しません。SYCL側のコメントでは、xe driverではgraph実行中のhost-mapped memoryへのkernel書き込みが安定して見えず、per-layer waitが失敗するため、NO_HOST時はwindow全体を待つと説明されています。ホストに処理させるexpertがある構成ではこの前提を満たせません。

起動時に初段のVRAM外expertについて、ミラーされなかった数を調べます。NO_HOSTが有効で不足が残ると、stderrに `strata generate: REFUSED: ...` を出して終了コード2にします。layer splitでも後段stageの不足を調べ、同様に拒否します。不足がなくても `--adapt-every` と `--adapt-swaps` が有効なら、stderrに `strata generate: adaptive swaps off: ...` を出し、`o.adapt_every` を0にします。

`sycl/serve/strata-sycl.sh` は `STRATA_VERIFY_DEVICE_PLAN=1`、`STRATA_VERIFY_NO_HOST=1`、`STRATA_STAGER_THREADS=12` を既定で渡します。スクリプト環境の値はこの既定値を上書きしますが、値が `0` または空文字ならコンテナへ渡しません。その場合、実行ファイル内では未設定としてOFFになります。サーバー設定の `env` ブロックも環境として渡される設計です。`sycl/setup_intel.py` はAlchemist/i915構成で `STRATA_VERIFY_NO_HOST=0` を設定し、layer splitでexpertが収まりそうにない場合も、設定で明示されていなければ `0` を設定します。

## ログと資料

拒否時の文言は `sycl/src/program/generate.cpp:4963-4965` および `5069-5074`、適応swap停止の文言は `4971-4974` です。SYCLラッパーの既定値と `0` の扱いは `sycl/serve/strata-sycl.sh:10-13,22-36` にあります。

`docs/INTEL.md:246-247` はNO_HOSTを「全window graphを待つ」設定と説明し、expertがすべてresidentの場合に限ると記しています。同資料の `:700-703` は値 `0` または空文字をOFFとして扱い、`strata-sycl.sh` がそれらを転送しない点を説明しています。コード上ではミラーに全missがある構成もdevice planが利用できるため、「全expertがVRAM resident」は一律の必須条件ではなく、各expertがVRAMまたはdevice planが参照可能なmirrorにあることが必要です。外部driverの内部動作や資料中の測定値は本調査の確認事実として扱っていません。

## 根拠

- `sycl/src/core/verify.cpp:795-801`: NO_HOST時のlean graph node省略条件。
- `sycl/src/core/verify.cpp:2178-2201`: SYCL window完了時のNO_HOST判定、層ごとのホスト待ち。
- `sycl/src/program/generate.cpp:4959-4975`: ミラーされないexpertの起動拒否とadaptive swap停止。
- `sycl/src/program/generate.cpp:5057-5078`: multi-GPU layer split後段の不足確認・拒否。
- `sycl/serve/strata-sycl.sh:10-13,22-36`: コンテナへの環境引き継ぎ、既定値および `0` / 空文字の除外。
- `sycl/setup_intel.py:207-216,308-321`: i915時の明示OFF、layer split時の不足予測に基づくOFF。
- `docs/INTEL.md:236-249,680-703,769-772`: SYCL利用方法、条件、値の扱いに関する説明。
