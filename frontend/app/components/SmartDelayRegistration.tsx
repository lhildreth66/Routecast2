/**
 * Smart Delay Trip Registration Component (Task E1 - Pro)
 *
 * Allows users to register planned trips for smart departure delay alerts.
 * Appears when user is premium and has created a route.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StyleSheet,
  Modal,
  ScrollView,
} from 'react-native';
import { useSmartDelay } from '../hooks/useSmartDelay';

interface SmartDelayRegistrationProps {
  visible: boolean;
  onClose: () => void;
  onSuccess?: (tripId: string) => void;
  subscriptionId: string;
  routeWaypoints: Array<{ latitude: number; longitude: number; name?: string }>;
  plannedDepartureLocal?: Date;
  userTimezone?: string;
  destinationName?: string;
}

/**
 * Component for registering a planned trip for smart delay alerts
 */
export const SmartDelayRegistration: React.FC<SmartDelayRegistrationProps> = ({
  visible,
  onClose,
  onSuccess,
  subscriptionId,
  routeWaypoints,
  plannedDepartureLocal,
  userTimezone = 'America/Denver',
  destinationName,
}) => {
  const {
    requestPermissions,
    registerToken,
    registerPlannedTrip,
    registrationLoading,
    registrationError,
  } = useSmartDelay();

  const [step, setStep] = useState<'welcome' | 'permissions' | 'registration'>(
    'welcome'
  );

  const handleRequestPermissions = useCallback(async () => {
    const granted = await requestPermissions();
    if (granted) {
      setStep('permissions');
      // Register token with backend
      const tokenRegistered = await registerToken(subscriptionId);
      if (tokenRegistered) {
        setStep('registration');
      } else {
        Alert.alert(
          'Token Error',
          'Failed to register notification token. Smart delay alerts may not work.'
        );
      }
    } else {
      Alert.alert(
        'Permission Denied',
        'Notification permissions are required for smart delay alerts.'
      );
    }
  }, [requestPermissions, registerToken, subscriptionId]);

  const handleRegisterTrip = useCallback(async () => {
    if (!plannedDepartureLocal || !routeWaypoints.length) {
      Alert.alert('Error', 'Planned departure time and route waypoints required');
      return;
    }

    const tripId = await registerPlannedTrip(
      {
        route_waypoints: routeWaypoints,
        planned_departure_local: plannedDepartureLocal.toISOString(),
        user_timezone: userTimezone,
        destination_name: destinationName,
      },
      subscriptionId
    );

    if (tripId) {
      Alert.alert(
        'Success',
        'Trip registered! You\'ll receive smart delay alerts if departing earlier would improve safety.'
      );
      onSuccess?.(tripId);
      handleClose();
    } else {
      Alert.alert(
        'Registration Error',
        registrationError || 'Failed to register planned trip'
      );
    }
  }, [
    registerPlannedTrip,
    subscriptionId,
    routeWaypoints,
    plannedDepartureLocal,
    userTimezone,
    destinationName,
    registrationError,
    onSuccess,
  ]);

  const handleClose = useCallback(() => {
    setStep('welcome');
    onClose();
  }, [onClose]);

  if (!visible) {
    return null;
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={handleClose}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={handleClose}
          >
            <Text style={styles.closeButtonText}>✕</Text>
          </TouchableOpacity>

          <ScrollView
            contentContainerStyle={styles.content}
            showsVerticalScrollIndicator={false}
          >
            {step === 'welcome' && (
              <>
                <Text style={styles.title}>Smart Departure Alerts</Text>
                <Text style={styles.subtitle}>Pro Feature</Text>

                <View style={styles.description}>
                  <Text style={styles.descriptionText}>
                    Get notified if delaying your departure by 1-3 hours would significantly reduce
                    weather hazards along your route.
                  </Text>

                  <View style={styles.benefits}>
                    <BenefitRow icon="📍" text="Route-aware forecasting" />
                    <BenefitRow
                      icon="⏰"
                      text="Smart 1-3 hour delay suggestions"
                    />
                    <BenefitRow icon="🌦️" text="Real-time hazard analysis" />
                    <BenefitRow icon="🔔" text="Push notifications to your device" />
                  </View>
                </View>

                <TouchableOpacity
                  style={styles.primaryButton}
                  onPress={handleRequestPermissions}
                >
                  <Text style={styles.primaryButtonText}>
                    Enable Smart Delays
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.secondaryButton}
                  onPress={handleClose}
                >
                  <Text style={styles.secondaryButtonText}>Not Now</Text>
                </TouchableOpacity>
              </>
            )}

            {step === 'permissions' && (
              <>
                <Text style={styles.title}>Setting Up Alerts...</Text>

                <View style={styles.statusContainer}>
                  <ActivityIndicator size="large" color="#eab308" />
                  <Text style={styles.statusText}>
                    Registering your device for notifications...
                  </Text>
                </View>
              </>
            )}

            {step === 'registration' && (
              <>
                <Text style={styles.title}>Ready for Smart Delays</Text>

                <View style={styles.successContainer}>
                  <Text style={styles.successEmoji}>✓</Text>
                  <Text style={styles.successText}>
                    Notifications enabled
                  </Text>
                </View>

                <View style={styles.tripInfo}>
                  <InfoRow
                    label="Departure"
                    value={
                      plannedDepartureLocal?.toLocaleTimeString() || 'Not set'
                    }
                  />
                  <InfoRow
                    label="Timezone"
                    value={userTimezone}
                  />
                  <InfoRow
                    label="Waypoints"
                    value={`${routeWaypoints.length} points`}
                  />
                  {destinationName && (
                    <InfoRow
                      label="Destination"
                      value={destinationName}
                    />
                  )}
                </View>

                {registrationError && (
                  <View style={styles.errorContainer}>
                    <Text style={styles.errorText}>{registrationError}</Text>
                  </View>
                )}

                <TouchableOpacity
                  style={[
                    styles.primaryButton,
                    registrationLoading && styles.buttonDisabled,
                  ]}
                  onPress={handleRegisterTrip}
                  disabled={registrationLoading}
                >
                  {registrationLoading ? (
                    <ActivityIndicator size="small" color="#000" />
                  ) : (
                    <Text style={styles.primaryButtonText}>
                      Confirm Registration
                    </Text>
                  )}
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.secondaryButton}
                  onPress={handleClose}
                  disabled={registrationLoading}
                >
                  <Text style={styles.secondaryButtonText}>Cancel</Text>
                </TouchableOpacity>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

/**
 * Benefit row component
 */
const BenefitRow: React.FC<{ icon: string; text: string }> = ({ icon, text }) => (
  <View style={styles.benefitRow}>
    <Text style={styles.benefitIcon}>{icon}</Text>
    <Text style={styles.benefitText}>{text}</Text>
  </View>
);

/**
 * Info row component
 */
const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.infoRow}>
    <Text style={styles.infoLabel}>{label}</Text>
    <Text style={styles.infoValue}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: '#000',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
    paddingTop: 20,
  },
  closeButton: {
    alignSelf: 'flex-end',
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  closeButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  content: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#eab308',
    fontWeight: '600',
    marginBottom: 20,
  },
  description: {
    marginBottom: 30,
  },
  descriptionText: {
    fontSize: 16,
    color: '#ccc',
    lineHeight: 24,
    marginBottom: 16,
  },
  benefits: {
    gap: 12,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  benefitIcon: {
    fontSize: 20,
    width: 30,
  },
  benefitText: {
    fontSize: 14,
    color: '#bbb',
    flex: 1,
  },
  primaryButton: {
    backgroundColor: '#eab308',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  secondaryButton: {
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#444',
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  statusContainer: {
    alignItems: 'center',
    marginVertical: 40,
  },
  statusText: {
    fontSize: 16,
    color: '#aaa',
    marginTop: 16,
    textAlign: 'center',
  },
  successContainer: {
    alignItems: 'center',
    marginVertical: 20,
  },
  successEmoji: {
    fontSize: 48,
    marginBottom: 8,
  },
  successText: {
    fontSize: 18,
    color: '#4ade80',
    fontWeight: '600',
  },
  tripInfo: {
    backgroundColor: '#111',
    borderRadius: 8,
    padding: 16,
    marginVertical: 20,
    gap: 12,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  infoLabel: {
    fontSize: 14,
    color: '#999',
  },
  infoValue: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '500',
  },
  errorContainer: {
    backgroundColor: '#7f1d1d',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 14,
    color: '#fca5a5',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
});
